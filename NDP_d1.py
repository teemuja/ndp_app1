# NDP app 1 boilerplate v0.1 beta a lot
import geopandas as gpd
import streamlit as st
import osmnx as ox
import plotly.express as px

header = '<p style="font-family:sans-serif; color:grey; font-size: 12px;">\
        NDP project app1 V0.75 "Betaman"\
        </p>'
st.markdown(header, unsafe_allow_html=True)

st.title("Urban efficiency (eu) studies..")
st.markdown("..using OSM data")
st.markdown("###")
st.latex(r'''
        eu_{m^2/GFA} = \left(\frac{\sum_{}^{m^2/GFA}}{\Pi*r^2}\right)
        ''') # https://katex.org/docs/supported.html
st.markdown("###")
add = st.text_input('Type address or place and the city', 'Otakaari 1 espoo')
radius = st.slider('Set the radius(m) how far the efficiency is calculated for each building', 200, 1500, 500, step=100)
floors = st.slider('Set average floor number for apartment buildings near the location', 1, 5, 2, step=1)

tags = {"building":True}
dist = radius * 2
gdf = ox.geometries_from_address(add, tags, dist)
fp_proj = ox.project_gdf(gdf).reset_index()
fp_poly = fp_proj[fp_proj["element_type"] == "way"]
fp_poly = fp_poly[["osmid","geometry","building"]]
fp_poly["area"] = fp_poly.area

# count building GFA using area and floor num average..
fp_poly["GFA"] = fp_poly["area"] * floors
# osm data too wrong for: fp_poly.loc[fp_poly.building.str.contains('apartments')] = fp_poly["area"] * floors
# dev ML function here
# ..but for small and large footprints use..
fp_poly.loc[fp_poly["area"] < 200,"GFA"] = fp_poly["area"] * 2
fp_poly.loc[fp_poly["area"] > 2000,"GFA"] = fp_poly["area"]

buff = gpd.GeoDataFrame(geometry=fp_poly.buffer(radius))
cents = gpd.GeoDataFrame(geometry=fp_poly.centroid)
cents["GFA"] = fp_poly["GFA"]
cents["osmid"] = fp_poly["osmid"]

# spatial join cent points in buffers..
agg = gpd.sjoin(cents,buff,how="inner",op="within").reset_index()
# groupby "same-buff-cents" (=index_right) and sum GFA values..
agg_group = agg.groupby('index_right').agg({'GFA':sum}).reset_index().rename(columns={'index_right':'index'})
agg_merge = agg.merge(agg_group,how='left', on='index').set_index("index")
fp_sum = fp_poly.merge(agg_merge,how='left', on='osmid').drop_duplicates(subset=['osmid'])

#clean and add footprint geometry back...
fp_sum = fp_sum[['osmid','geometry_x','building','area','GFA_y','GFA']].\
    rename(columns={'geometry_x':'geometry','area':'footprint area','GFA_y':'GFA nearby'})
fp_gdf = gpd.GeoDataFrame(fp_sum, geometry="geometry").reset_index(drop=True)

# import ML script here!
fp_gdf['efficiency'] = fp_gdf['GFA nearby'] / fp_gdf.buffer(radius).area

# cut out edge footprints (incomplete sum values) and viz circle..
union = fp_poly.unary_union
env = union.envelope
focus = gpd.GeoSeries(env)
focus_area = gpd.GeoSeries(focus)
focus_circle = focus_area.centroid.buffer(radius)

focus_gdf = gpd.GeoDataFrame(focus_circle, geometry=0)
fp_cut = gpd.overlay(fp_gdf, focus_gdf, how='intersection') # CRS mismatch here?

# viz table of describe..
st.subheader('Query data described')
st.dataframe(fp_cut.drop(columns=["geometry","osmid"]).describe().T)
sourceinfo = '<p style="font-family:sans-serif; color:grey; font-size: 9px;">\
        Values other than footprint area are based on machine learning estimates.\
        </p>'
st.markdown(sourceinfo, unsafe_allow_html=True)

# prep map..
geo_df = fp_cut.to_crs(4326)
# define center of data..
bbox = geo_df.total_bounds
lat = (bbox[1] + (bbox[3] - bbox[1]))
lon = (bbox[0] + (bbox[2] - bbox[0]))

st.subheader('Choropleth map')
fig = px.choropleth_mapbox(geo_df,
                    geojson=geo_df.geometry,
                    locations=geo_df.index,
                    color="efficiency",
                    hover_name="building",
                    #hover_data='GFA nearby',
                    mapbox_style="carto-positron",
                    color_continuous_scale="Reds",
                    center={"lat": lat, "lon": lon},
                    zoom = 13,
                    width = 800,
                    height = 600
                    )

st.plotly_chart(fig)


footer_title = '''
---
:see_no_evil: **Naked Density Project** ([NDP](https://github.com/teemuja?tab=projects))
'''
st.markdown(footer_title) # https://gist.github.com/rxaviers/7360908

footer_eng = '<p style="font-family:sans-serif; color:black; font-size: 12px;">\
        ENG: Naked Density Project is a research project by Teemu Jama in Aalto University Finland.\
        NDP project studies correllations between land use typologies and urban amenities\
        by applying latest spatial data analytics and machine learning. \
        </p>'

footer_fin = '<p style="font-family:sans-serif; color:grey; font-size: 12px;">\
        FIN: Naked Density Projekti on osa Teemu Jaman väitöskirjatutkimusta Aalto Yliopistossa. \
        Projektissa tutkitaan maankäytön tehokkuuden ja kaupunkirakenteen fyysisten piirteiden\
        vaikutuksia palveluiden kehittymiseen \
        data-analytiikan ja koneoppimisen avulla.\
        </p>'

st.markdown(footer_eng, unsafe_allow_html=True)
st.markdown(footer_fin, unsafe_allow_html=True)

# TODO
# 1. calculate el using only build-up areas (exclude parks and water bodies)
#   1b define build-up area using footprint density ..dist to the next footprint ..like finnish concept "taajama"
# 2. add "save to github -button" to save query to repo
# 3. dev ML function for building type estimation by footprint size
# 4. add functions & layer for "functional efficiency" using OSM amenities
# 5.