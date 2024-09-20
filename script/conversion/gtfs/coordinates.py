from pyproj import Transformer


def gps_to_lambert93(lat, lon):
    # Create a transformer for EPSG:4326 (WGS84) to EPSG:5698 (Lambert 93 CC46)
    transformer = Transformer.from_crs("epsg:4326", "epsg:5698", always_xy=True)

    # Transform coordinates from WGS84 to Lambert 93
    x, y = transformer.transform(lon, lat)

    return x, y


def gps_to_utm(lat, lon):
    # Determine UTM zone for the longitude
    utm_zone = int((lon + 180) / 6) + 1
    # Define hemisphere (Northern for lat > 0, Southern for lat < 0)
    hemisphere = 'north' if lat >= 0 else 'south'

    # Create a transformer for WGS84 to UTM based on the calculated zone and hemisphere
    transformer = Transformer.from_crs("epsg:4326",
                                       f"epsg:326{utm_zone}" if hemisphere == 'north' else f"epsg:327{utm_zone}",
                                       always_xy=True)

    # Perform the transformation
    x, y = transformer.transform(lon, lat)

    return x, y