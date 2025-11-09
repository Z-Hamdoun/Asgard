from geopy.distance import distance, geodesic
from geopy.point import Point
from math import atan2, sqrt, degrees

def conv_cart_to_geo(
        xi : tuple[float, float],
        x : tuple[float, float]
    ) -> tuple[float, float]:
    """Convertion des coordonnées cartésiennes en géographiques.

    Args:
        xi (tuple[float, float]): (latitude, longitude) du point de référence.
        x (tuple[float, float]): (deplacement vers le Nord , deplacement vers l'Est) déplacement par rapport au point d'origine.

    Returns:
        tuple:
            - **latitude** (*float*) – Latitude du point final.
            - **longitude** (*float*) – Longitude du point final.
    """
    start_point = Point(xi[0], xi[1])

    # Calculate the distance and bearing
    distance_meters = sqrt(x[0]**2 + x[1]**2)  # Pythagorean theorem
    bearing = degrees(atan2(x[1], x[0]))  # Bearing from north (0 degrees)

    # Calculate the new latitude and longitude
    new_point = distance(meters=distance_meters).destination(start_point, bearing)
    return new_point.latitude, new_point.longitude

# Pas vraiment testé
def deplacement_nord_est(
        x_i: tuple[float, float],
        x_f: tuple[float, float]
    ) -> tuple[float, float]:
    """
    Calcule les déplacements en mètres vers le Nord et vers l'Est
    pour aller de x_i à x_f.

    Args:
        x_i (tuple[float, float]): (lat_i, lon_i) en degrés.
        x_f (tuple[float, float]): (lat_f, lon_f) en degrés.

    Returns:
        tuple:
            - **delta_nord** (*float*) – Déplacement Nord en m.
            - **delta_est** (*float*) – Déplacement Est en m.
    """
    lat_i, lon_i = x_i
    lat_f, lon_f = x_f

    # Déplacement Nord (différence de latitude, même longitude)
    point_nord = (lat_f, lon_i)
    delta_nord = geodesic(x_i, point_nord).meters
    if lat_f < lat_i:
        delta_nord *= -1

    # Déplacement Est (différence de longitude, même latitude)
    point_est = (lat_i, lon_f)
    delta_est = geodesic(x_i, point_est).meters
    if lon_f < lon_i:
        delta_est *= -1

    return delta_nord, delta_est
