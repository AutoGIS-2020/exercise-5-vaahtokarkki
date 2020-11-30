import geopandas as gpd
from shapely.geometry import Polygon
import time
import folium


def overlay(gdf, mask, how):
    assert gdf.crs.to_wkt() == mask.crs.to_wkt(), "Mask and df CRS does not match"
    print("Starting clipping")
    start_time = time.time()
    clipped_gdf = gpd.overlay(gdf, mask, how=how)
    print("Clip took",
          time.strftime("%M min, %S sec", time.gmtime(time.time() - start_time)))
    return clipped_gdf


def sum_by(df, column, output_column):
    df[output_column] = df[column].sum()
    return df


def calc(row):
    dist = row["distance"]
    summ = row["sum"]
    if dist < 1:
        return 0
    return summ / dist


# Simple mask to clip out Vantaa which is not part of city bikes
mask_polygon = Polygon([[24.7, 60.143], [24.7, 60.247], [25.128, 60.247],
                        [25.128, 60.143]])
mask = gpd.GeoDataFrame(index=[0], crs={'init': 'epsg:4326'}, geometry=[mask_polygon]) \
    .to_crs(epsg=4326)

population = gpd.read_file("data/Pks_vaki.shp").to_crs(epsg=4326)
clipped_grid = gpd.read_file('data/clipped_grid.shp').to_crs(epsg=4326)
stations = gpd.read_file('data/citybike_stations.shp').to_crs(epsg=3857)
# Layer from previous problem
citybikes_matrix = gpd.read_file('data/citybikes_matrix.shp').to_crs(epsg=4326)

grid_small = overlay(clipped_grid, mask, "intersection").to_crs(epsg=4326)
grid_small["polygons"] = grid_small.geometry  # Copy grid polygons to new column

# Get population to grid elements
points_joined = gpd.sjoin(population, grid_small, how="inner", op="within")
points_joined = points_joined.groupby("YKR_ID") \
    .apply(sum_by, column="ASYHT", output_column="sum")

grid_joined = gpd.GeoDataFrame(points_joined, geometry=points_joined["polygons"],
                               crs={'init': 'epsg:4326'}).to_crs(epsg=4326)


# Filter out squares with too low population
grid_joined = grid_joined[grid_joined["sum"] > 20]

# Join data from previous problem
data_joined = grid_joined.merge(citybikes_matrix, on="YKR_ID", how="left")
data_joined = data_joined[data_joined["distance"] > 200] # Filter out squares with station
data_joined["station_index"] = data_joined.apply(calc, axis=1) # Calculate index

# Autoscaling, https://en.wikipedia.org/wiki/Standard_score
data_joined["station_index"] = (data_joined["station_index"] - data_joined["station_index"].mean())/data_joined["station_index"].std()
data_joined = data_joined[data_joined["station_index"] > 0] # Filter out values bellow mean
data_joined = gpd.GeoDataFrame(data_joined, geometry=data_joined["geometry_y"],
                               crs={'init': 'epsg:4326'}).to_crs(epsg=4326)

data_for_map = data_joined[["station_index", "geometry", "YKR_ID"]]
data_for_map['geoid'] = data_for_map.index.astype(str)

m = folium.Map(location=[60.2, 24.9], tiles = 'cartodbpositron', zoom_start=13, control_scale=True)
points_gjson = folium.features.GeoJson(stations)
layer = folium.FeatureGroup(name='Stations', show=False)

# HACK
# https://stackoverflow.com/a/53816162
for feature in points_gjson.data['features']:
    if feature['geometry']['type'] == 'Point':
        folium.CircleMarker(
            location=list(reversed(feature['geometry']['coordinates'])),
            radius=5,
            fill_color="#00000",
            fill=True,
            stroke=False
        ).add_to(layer)
layer.add_to(m)

folium.Choropleth(
    geo_data=data_for_map,
    name='Where to insert a new bike station',
    data=data_for_map,
    columns=['geoid', 'station_index'],
    key_on='feature.id',
    fill_color='Reds',
    fill_opacity=0.7,
    highlight=False,
    smooth_factor=1.0,
    line_opacity=0,
    legend_name='Autoscaled population / dist').add_to(m)

title_html = '''<div style="padding: .5rem 10%;position: absolute;top: 10px;z-index: 9999999999;background-color: #ffffff70;">
<h4>Where to build bike station based on distance to closest station and population?</h4><p>
    <br>Grid elements containing a bike station is filtered out and
     for remaining squares a index is calculated. Index is calculated by population of
     square divided by distance from center of square to closest bike station.<br>
     This yields greater value for high population squares ar away from an existing bike
     station. The index is normalized by autoscaling and values bellow zero is filtered
     out. This means squares with better situation (low pop and close to station) is
     filtered out, as zero represents mean after autoscale.</p></div>'''
m.get_root().html.add_child(folium.Element(title_html))

m.save('docs/index.html')
