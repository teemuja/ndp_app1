# NDP app 1 boilerplate v0.2 beta a lot
import pandas as pd
import geopandas as gpd
import streamlit as st
import osmnx as ox
import momepy
import plotly.express as px

# page setup
st.set_page_config(page_title="NDP App d1", layout="wide")
padding = 2
st.markdown(f""" <style>
    .reportview-container .main .block-container{{
        padding-top: {padding}rem;
        padding-right: {padding}rem;
        padding-left: {padding}rem;
        padding-bottom: {padding}rem;
    }} </style> """, unsafe_allow_html=True)

header = '<p style="font-family:sans-serif; color:grey; font-size: 12px;">\
        NDP project app1 V0.88 "Global Betaman"\
        </p>'
st.markdown(header, unsafe_allow_html=True)
# plot size setup
#px.defaults.width = 600
px.defaults.height = 600

# page title
header_title = '''
:see_no_evil: **Naked Density Project**
'''
st.subheader(header_title)
header_text = '''
<p style="font-family:sans-serif; color:Dimgrey; font-size: 12px;">
Naked Density Project is a PhD research project by <a href="https://github.com/teemuja" target="_blank">Teemu Jama</a> in Aalto University Finland.  
NDP project studies correlation between land use typologies and <a href="https://sdgs.un.org/goals" target="_blank">SDG-goals</a> by applying latest spatial data analytics and machine learning. \
</p>
'''
st.markdown(header_text, unsafe_allow_html=True)
st.markdown("----")

st.title("Data Paper #0.88")
st.markdown("Density metrics using OSM data")
st.markdown("###")

add = st.text_input('Type address or place and the city', 'Otakaari 1 espoo')
#floors = st.slider('Explore the effect of GFA by changing average floor number of buildings near the location', 1, 9, 2, step=1)
sourceinfo = '<p style="font-family:sans-serif; color:grey; font-size: 9px;">\
        ...\
        </p>'
st.markdown(sourceinfo, unsafe_allow_html=True)

tags = {"building":True}
radius = 1000
gdf = ox.geometries_from_address(add, tags, radius)
fp_proj = ox.project_gdf(gdf).reset_index()
fp_poly = fp_proj[fp_proj["element_type"] == "way"]
fp_poly = fp_poly[["osmid","geometry","building",'building:levels']]
fp_poly["area"] = fp_poly.area

fp_poly["building:levels"] = pd.to_numeric(fp_poly["building:levels"], errors='coerce', downcast='float')
# replace this with ML-function when ready..
if fp_poly["building:levels"] is not None or (fp_poly["building:levels"] == 0):
    fp_poly["GFA"] = fp_poly["area"] * fp_poly["building:levels"]
else:
    fp_poly["GFA"] = fp_poly["area"]

@st.cache(allow_output_mutation=True)
def osm_densities(buildings):
    # projected crs for momepy calculations
    gdf = buildings.to_crs(3857)
    #gdf_['GFA'] = pd.to_numeric(gdf_['GFA'], errors='coerce', downcast='float')
    #gdf_['GFA'].fillna(gdf_.area, inplace=True)
    gdf['uID'] = momepy.unique_id(gdf)
    limit = momepy.buffered_limit(gdf)
    tessellation = momepy.Tessellation(gdf, unique_id='uID', limit=limit).tessellation
    # calculate GSI = ground space index = coverage = CAR = coverage area ratio
    tess_GSI = momepy.AreaRatio(tessellation, gdf,
                                momepy.Area(tessellation).series,
                                momepy.Area(gdf).series, 'uID')
    gdf['GSI'] = round(tess_GSI.series,3)
    # calculate FSI = floor space index = FAR = floor area ratio
    gdf['FSI'] = round(gdf['GFA'] / momepy.Area(tessellation).series,3)
    # calculate OSR = open space ratio = spaciousness
    gdf['OSR'] = round((1 - gdf['GSI']) / gdf['FSI'],3)
    # calculate average GSI of nearby plots
    # queen contiguity for 2 degree neighbours = "perceived neighborhood"
    tessellation = tessellation.merge(gdf[['uID', 'OSR']])  # add OSR values to tesselation areas for calculation below
    sw = momepy.sw_high(k=2, gdf=tessellation, ids='uID')
    # add median OSR of "perceived neighborhood" for each building
    gdf['OSR_ND'] = momepy.AverageCharacter(tessellation, values='OSR', spatial_weights=sw, unique_id='uID').mean
    gdf['OSR_ND'] = round(gdf['OSR_ND'],2)
    #gdf_out = gdf.to_crs(4326)
    return gdf

density_data = osm_densities(fp_poly)

# cut out edge footprints (incomplete sum values) and viz circle..
union = fp_poly.to_crs(3857).unary_union
env = union.envelope
focus = gpd.GeoSeries(env)
focus_area = gpd.GeoSeries(focus)
focus_circle = focus_area.centroid.buffer(radius)

focus_gdf = gpd.GeoDataFrame(focus_circle, geometry=0)
fp_cut = gpd.overlay(density_data, focus_gdf, how='intersection') # CRS projected for both

# crs back to 4326
case_data = fp_cut.to_crs(4326)

def classify_density(density_data):
    density_data['OSR_class'] = 'very dense'
    density_data.loc[density_data['OSR'] > 2, 'OSR_class'] = 'dense'
    density_data.loc[density_data['OSR'] > 10, 'OSR_class'] = 'spacious'
    density_data.loc[density_data['OSR'] > 20, 'OSR_class'] = 'scattered'
    density_data['OSR_ND_class'] = 'very dense'
    density_data.loc[density_data['OSR_ND'] > 2, 'OSR_ND_class'] = 'dense'
    density_data.loc[density_data['OSR_ND'] > 10, 'OSR_ND_class'] = 'spacious'
    density_data.loc[density_data['OSR_ND'] > 20, 'OSR_ND_class'] = 'scattered'
    return density_data

colormap_osr = {
    "very dense": "chocolate",
    "dense": "darkgoldenrod",
    "spacious": "darkolivegreen",
    "scattered": "cornflowerblue"
}

# plot function
def create_plot(density_data,osr_ve):
    if osr_ve == 'Plot OSR':
        @st.cache
        def plot_with_osr(density_data):
            fig_dens = px.scatter(density_data, title='Density nomogram',
                                  x='GSI', y='FSI', color='OSR_class', #size='building:levels',
                                  log_y=False,
                                  hover_name='building',
                                  hover_data=['GFA', 'FSI', 'GSI', 'OSR', 'OSR_ND'],
                                  labels={"OSR_class": f'{osr_ve}'},
                                  color_discrete_map=colormap_osr
                                  )
            fig_dens.update_layout(legend={'traceorder': 'normal'})
            fig_dens.update_layout(xaxis_range=[0, 0.5], yaxis_range=[0, 2])
            fig_dens.update_xaxes(rangeslider_visible=True)
            return fig_dens
        fig_out = plot_with_osr(density_data)

    else:
        @st.cache
        def plot_with_osr_nd(density_data):
            fig_dens = px.scatter(density_data, title='Density nomogram',
                                  x='GSI', y='FSI', color='OSR_class', #size='building:levels',
                                  log_y=False,
                                  hover_name='building',
                                  hover_data=['GFA', 'FSI', 'GSI', 'OSR', 'OSR_ND'],
                                  labels={"OSR_class": f'{osr_ve}'},
                                  color_discrete_map=colormap_osr
                                  )
            fig_dens.update_layout(legend={'traceorder': 'normal'})
            fig_dens.update_layout(xaxis_range=[0, 0.5], yaxis_range=[0, 2])
            fig_dens.update_xaxes(rangeslider_visible=True)
            return fig_dens
        fig_out = plot_with_osr_nd(density_data)
    return fig_out

# classify
density_data = classify_density(case_data)

# plot spot
plot_spot = st.empty()

# select plot type
osr_ve = st.radio("Select scale of OSR", ('Plot OSR', 'Neighborhood OSR'))

if osr_ve == 'Plot OSR':
    plot = create_plot(case_data,'Plot OSR')
    plot_spot.plotly_chart(plot, use_container_width=True)
else:
    plot = create_plot(case_data, 'Neighborhood OSR')
    plot_spot.plotly_chart(plot, use_container_width=True)


st.markdown('-------------')
# map container
with st.expander("Densities on map", expanded=False):
    map_spot = st.empty()
    def density_map(plot):
        if osr_ve == 'Plot OSR':
            mapcolor = plot['OSR_class']
        else:
            mapcolor = plot['OSR_ND_class']
        lat = plot.unary_union.centroid.y
        lon = plot.unary_union.centroid.x
        map = px.choropleth_mapbox(plot,
                                   geojson=plot.geometry,
                                   locations=plot.index,
                                   color=mapcolor,
                                   hover_name="building",
                                   hover_data=['GFA', 'FSI', 'GSI', 'OSR', 'OSR_ND','building:levels'],
                                   mapbox_style="carto-positron",
                                   labels={'OSR_class': 'Plot OSR','OSR_ND_class': 'Neighborhood OSR'},
                                   color_discrete_map=colormap_osr,
                                   center={"lat": lat, "lon": lon},
                                   zoom=13,
                                   opacity=0.8,
                                   width=1200,
                                   height=700
                                   )
        map.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=700)
        return map
    # plot
    with map_spot:
        st.plotly_chart(density_map(case_data), use_container_width=True)



footer_title = '''
---
:see_no_evil: **Naked Density Project**
[![MIT license](https://img.shields.io/badge/License-MIT-yellow.svg)](https://lbesson.mit-license.org/) 
'''
st.markdown(footer_title)