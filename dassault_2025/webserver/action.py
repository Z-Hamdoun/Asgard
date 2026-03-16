
GLOBAL_SYSTEM_ID = 0
DRONE_ID = 1
AIRCRAFT_ID = 3

ACTION_CONNEXTION           = 5
ACTION_DECONEXTION          = 6
ACTION_ARMING               = 7
ACTION_TAKEOFF              = 8
ACTION_LANDING              = 9
ACTION_DISARM_FORCE         = 10
ACTION_SEND_GPS_PT          = 11
ACTION_END_GPS_PT           = 12
ACTION_STOP_MISSION         = 13
ACTION_RESTART              = 14
ACTION_OPEN_LOADING_MODULE  = 15
ACTION_CLOSE_LOADING_MODULE = 16 
RESET_CGM                   = 17
M_TRAJECTOIRE_AVION         = 18
M_LARGAGE_MASSE_MORTE       = 19
M_TRAJECTOIRE_DRONE         = 20
M_QUADRILLAGE               = 21
M_ASSERVISSEMENT_ARUCO      = 22
M_QUADRILLAGE_ARUCO         = 23
M_LARGAGE                   = 24
M_LARGAGE_QUADRILLAGE       = 25
M_LARGAGE_QUADRILLAGE_ARUCO = 26
ACTION_RTL                  = 27
ACTION_GIT_PULL             = 28
M_FOLLOW_AVION_DRONE        = 29
ACTION_FOLLOW               = 32

ACTION_WRITE_PARAMETERS     = 30
ACTION_REFRESH_PARAMETERS   = 31

DRONE_PARAMS = [
    {'id': 1,  'label': 'vrai_largage'         , 'default': 'True' , 'type': 'bool'},
    {'id': 2,  'label': 'taille_quadrillage'   , 'default': '10'   , 'type': 'float'},
    {'id': 3,  'label': 'radius_acceptance'    , 'default': '1'    , 'type': 'float'},
    {'id': 4,  'label': 'camera.aruco_size'    , 'default': '0.36' , 'type': 'float'},
    {'id': 5,  'label': 'camera.aruco_id'      , 'default': '4'    , 'type': 'int'},
    {'id': 6,  'label': 'magic_value'          , 'default': '0'    , 'type': 'int'},
    {'id': 10, 'label': 'camera.DO_CROP'       , 'default': 'True' , 'type': 'bool'},
    {'id': 11, 'label': 'pas_quadrillage'      , 'default': '2'    , 'type': 'float'},
    {'id': 12, 'label': 'FOLLOW_MAX_SPEED'     , 'default': '1400' , 'type': 'int'},
    {'id': 13, 'label': 'WPNAV_SPEED'          , 'default': '200'  , 'type': 'int'},
    {'id': 15, 'label': 'alt_quadrillage'      , 'default': '8'    , 'type': 'float'}
]

AIRCRAFT_PARAMS = [
    {'id': 7,  'label': 'distance_before_largage' , 'default': '40' , 'type': 'float'},
    {'id': 8,  'label': 'accept_radius'           , 'default': '10' , 'type': 'float'},
    {'id': 9,  'label': 'servo_channel_rc'        , 'default': '7'  , 'type': 'int'},
    {'id': 14, 'label': 'takeoff_pitch'           , 'default': '15' , 'type': 'float'},
    {'id': 16, 'label': 'takeoff_alt'             , 'default': '10' , 'type': 'float'}
]

MARKER_TYPES = [
    "largage",
    "waypoint"
]