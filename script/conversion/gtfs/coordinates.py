from pyproj import Proj, Transformer, transform


def gps_to_lambert93(lat, lon):
    # Create a transformer for EPSG:4326 (WGS84) to EPSG:5698 (Lambert 93 CC46)
    transformer = Transformer.from_crs("epsg:4326", "epsg:5698", always_xy=True)

    # Transform coordinates from WGS84 to Lambert 93
    x, y = transformer.transform(lon, lat)

    return x, y


def gps_to_utm(lat, lon):
    # Determine the UTM zone based on the longitude
    utm_zone = int((lon + 180) // 6) + 1
    # Define the UTM projection for the correct zone, assuming the Northern Hemisphere
    utm_proj = Proj(proj='utm', zone=utm_zone, ellps='WGS84', south=False)
    # Define WGS84 (standard GPS) projection
    wgs84 = Proj('epsg:4326')

    # Transform coordinates from WGS84 to UTM
    x, y = transform(wgs84, utm_proj, lon, lat)

    return x, y