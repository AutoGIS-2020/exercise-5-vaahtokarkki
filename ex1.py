import geopandas as gpd
from matplotlib import pyplot as plt
from matplotlib.pyplot import legend
from shapely.geometry import Polygon
import time
import mapclassify
import contextily as ctx
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

def get_nearest(point, points):
    # nearest_points() is too slow.....
    # return points[
    #     points["geometry"] == nearest_points(point, points.geometry.unary_union)[1]
    # ].geometry.values[0]
    return min([point.distance(p) for p in points])


def overlay(gdf, mask, how):
    assert gdf.crs.to_wkt() == mask.crs.to_wkt(), "Mask and df CRS does not match"
    print("Starting clipping")
    start_time = time.time()
    clipped_gdf = gpd.overlay(gdf, mask, how=how)
    print("Clip took",
          time.strftime("%M min, %S sec", time.gmtime(time.time() - start_time)))
    return clipped_gdf

# This part clips out sea from the grid
# sea = gpd.read_file('data/m_meri.shp').to_crs("EPSG:4326")
# grid = gpd.read_file("data/MetropAccess_YKR_grid_EurefFIN.shp")
# clipped_grid = overlay(grid, sea, "difference")
# clipped_grid.to_file(driver='ESRI Shapefile', filename= "data/clipped_grid.shp")


clipped_grid = gpd.read_file('data/clipped_grid.shp').to_crs(epsg=4326)

# Simple mask to clip out Vantaa which is not part of city bikes
mask_polygon = Polygon([[24.7, 60.143], [24.7, 60.247], [25.128, 60.247],
                        [25.128, 60.143]])
mask = gpd.GeoDataFrame(index=[0], crs={'init': 'epsg:4326'}, geometry=[mask_polygon]) \
    .to_crs(epsg=4326)

grid_small = overlay(clipped_grid, mask, "intersection").to_crs(epsg=3310)
stations = gpd.read_file('data/citybike_stations.shp').to_crs(epsg=3310)

station_points = stations.geometry.tolist()
print("Calculating distances")
grid_small["min"] = grid_small.apply(
    lambda row: get_nearest(row.geometry.centroid, station_points), axis=1
)
print("Distances done")

grid_small = grid_small.to_crs(epsg=3857)
stations = stations.to_crs(epsg=3857)
classifier = mapclassify.UserDefined.make(bins=[250, 800])
grid_small["min"] = grid_small[["min"]].apply(classifier)

print("Plotting the map")
ax = grid_small.plot(column="min", cmap="RdYlBu", linewidth=0, alpha=0.6,
                     figsize=(30, 20))
stations.plot(ax=ax, markersize=3, color="black")
ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)

LegendElement = [
    mpatches.Patch(color='#A50026', label='<3min'),
    mpatches.Patch(color='#FFF7B3', label='3-8min'),
    mpatches.Patch(color='#323896', label='>8min'),
    Line2D([0], [0], marker='o', color='black', label='Bike station',
           markerfacecolor='g', markersize=3)
]

ax.legend(handles=LegendElement)
# Crop the map according grid
minx, miny, maxx, maxy = grid_small.total_bounds
ax.set_xlim(minx, maxx)
ax.set_ylim(miny, maxy)

plt.title("Walking time matrix for HSL city bike stations")
plt.savefig('docs/problem_1.png', dpi=300)
plt.show()
