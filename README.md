# Macro à ajouter

Si vous n'utilisez pas le pack de macros disponible [ici](https://github.com/CIS94500/Klipper-Config-ANYCUBIC-VYPER/), vous devez ajouter ces deux macros à votre configuration.

```
[gcode_macro _START_CALIBRATE_PROBE]  
description: Calibration de la jauge  
gcode:  
  {% if printer.idle_timeout.state == "Printing" %}  
    RESPOND TYPE=error MSG="Interdiction de faire la calibration !"  
  {% else %}  
    {% set x_size = printer.toolhead.axis_maximum.x|float / 2 %}  
    {% set y_size = printer.toolhead.axis_maximum.y|float / 2 %}  
    probe_reset  
    SET_GCODE_OFFSET Z=0  
    G28  
    G1 X{x_size} Y{y_size} F6000  
    PROBE_CALIBRATE  
  {% endif %}  
```
```
[gcode_macro _BED_LEVELING]  
description: Nivellement du plateau  
gcode:  
  {% if printer.idle_timeout.state == "Printing" %}  
    RESPOND TYPE=error MSG="Interdiction de faire le leveling !"  
  {% else %}  
    {% if printer.heater_bed.temperature < 50 %}  
      RESPOND MSG="Mise en chauffe du plateau..."  
    {% endif %}  
      M190 S50  
      G28  
      BED_MESH_CALIBRATE  
      G1 Z20 F3600  
      G1 X0 Y0 F6000  
      TURN_OFF_HEATERS  
      SAVE_CONFIG  
 {% endif %}  
```

# KlipperScreen

KlipperScreen is a touchscreen GUI that interfaces with [Klipper](https://github.com/kevinOConnor/klipper) via [Moonraker](https://github.com/arksine/moonraker). It can switch between multiple printers to access them from a single location, and it doesn't even need to run on the same host, you can install it on another device and configure the IP address to access the printer.

### Documentation [![Documentation Status](https://readthedocs.org/projects/klipperscreen/badge/?version=latest)](https://klipperscreen.readthedocs.io/en/latest/?badge=latest)

[Click here to access the documentation.](https://klipperscreen.readthedocs.io/en/latest/)

### Inspiration
KlipperScreen was inspired by [OctoScreen](https://github.com/Z-Bolt/OctoScreen/) and the need for a touchscreen GUI that
will natively work with [Klipper](https://github.com/kevinOConnor/klipper) and [Moonraker](https://github.com/arksine/moonraker).

[![Main Menu](docs/img/panels/main_panel.png)](https://klipperscreen.readthedocs.io/en/latest/Panels/)

[More Screenshots](https://klipperscreen.readthedocs.io/en/latest/Panels/)