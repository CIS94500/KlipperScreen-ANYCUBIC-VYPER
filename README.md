# KlipperScreen

### Documentation [![Documentation Status](https://readthedocs.org/projects/klipperscreen/badge/?version=latest)](https://klipperscreen.readthedocs.io/en/latest/?badge=latest)

[![Main Menu](docs/img/panels/main_panel.png)](https://klipperscreen.readthedocs.io/en/latest/Panels/)

[More Screenshots](https://klipperscreen.readthedocs.io/en/latest/Panels/)  

# Macro à ajouter

Si vous n'utilisez pas le pack de macros disponible [ici](https://github.com/CIS94500/Klipper-Config-ANYCUBIC-VYPER/), vous devez ajouter ces macros à votre configuration.

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
		RESPOND TYPE=error MSG="Impossible de faire le leveling pendant une impression !"
	{% else %}
		{% set temp_bed = 60 %}
		{% if printer.heater_bed.temperature < temp_bed %}
			RESPOND MSG="Mise en chauffe du plateau à {temp_bed}°C"
		{% endif %}
		M190 S{temp_bed}
		RESPOND MSG="Patientez 3 min supplémentaires pour un chauffe uniforme du plateau.."
		G4 P180000
		SET_GCODE_OFFSET Z=0
		G28
		BED_MESH_CALIBRATE
		G1 Z20 F3600
		G1 X0 Y0 F6000
		TURN_OFF_HEATERS
		SAVE_CONFIG
	{% endif %} 
```
```
[gcode_macro _EXTRUDE]
description: Extrusion du filament (KlipperScreen "VS")
gcode:
	{% set direction = params.DIR|default("+") %}
	{% set distance = params.DIST|default(50)|float %}
	{% set speed = params.SPEED|default(400)|float %}
	{% if printer.idle_timeout.state == "Printing" and not printer.pause_resume.is_paused %}
		RESPOND TYPE=error MSG="Impossible d'extruder le filament pendant une impression !"
	{% else %}
		{% if printer["filament_switch_sensor filament_sensor"].filament_detected == True or printer["filament_switch_sensor filament_sensor"].enabled == False %}
			{% set temp_extruder = printer.extruder.temperature|int %}
			{% set temp_min_extrude = printer.configfile.settings['extruder'].min_extrude_temp|int %}
			{% set temp_cible = temp_min_extrude + 10 %}
			{% if printer.extruder.target|int > temp_min_extrude  %}
				{% set temp_cible = printer.extruder.target|int %}
			{% elif temp_extruder < temp_min_extrude  %}
				RESPOND MSG="Mise en chauffe de la buse à {temp_cible}°C"
			{% endif %}
			{% if "xyz" in printer.toolhead.homed_axes %}
				SAVE_GCODE_STATE NAME=EXTRUDE_state
			{% endif %}
			G91
			M106 S0
			M104 S{temp_cible}
			{% if temp_extruder < (temp_cible - 5) %} M109 S{temp_cible} {% endif %}
			G0 E{direction}{distance} F{speed}
			{% if "xyz" in printer.toolhead.homed_axes %}
				M400
				RESTORE_GCODE_STATE NAME=EXTRUDE_state MOVE=0
			{% endif %}
		{% else %}
			RESPOND TYPE=error MSG="Veuillez insérer du filament !"
		{% endif %}
	{% endif %}
```
```
[delayed_gcode LOAD_GCODE_OFFSETS]
initial_duration: 2
gcode:
	{% if printer.save_variables.variables.gcode_offsets %}
		{% set offsets = printer.save_variables.variables.gcode_offsets %}
		_SET_GCODE_OFFSET {% for axis, offset in offsets.items() if offsets[axis] %}{ "%s=%s " % (axis, offset) }{% endfor %}
		{ action_respond_info("Loaded gcode offsets from saved variables [%s]" % (offsets)) }
	{% endif %}
```
```
[gcode_macro SET_GCODE_OFFSET]
rename_existing: _SET_GCODE_OFFSET
gcode:
	{% if printer.save_variables.variables.gcode_offsets %}
		{% set offsets = printer.save_variables.variables.gcode_offsets %}
	{% else %}
		{% set offsets = {'x': None,'y': None,'z': None} %}
	{% endif %}
	{% set ns = namespace(offsets={'x': offsets.x,'y': offsets.y,'z': offsets.z}) %}
	_SET_GCODE_OFFSET {% for p in params %}{'%s=%s '% (p, params[p])}{% endfor %}
	{%if 'X' in params %}{% set null = ns.offsets.update({'x': params.X}) %}{% endif %}
	{%if 'Y' in params %}{% set null = ns.offsets.update({'y': params.Y}) %}{% endif %}
	{%if 'Z' in params %}{% set null = ns.offsets.update({'z': params.Z}) %}{% endif %}
	{%if 'Z_ADJUST' in params %}
	{%if ns.offsets.z == None %}{% set null = ns.offsets.update({'z': 0}) %}{% endif %}
		{% set null = ns.offsets.update({'z': (ns.offsets.z | float) + (params.Z_ADJUST | float)}) %}
	{% endif %}
	SAVE_VARIABLE VARIABLE=gcode_offsets VALUE="{ns.offsets}"
```
```
[save_variables]
filename: /home/pi/printer_data/config/var.cfg
```

>Vous devez aussi créer le fichier /home/pi/printer_data/config/var.cfg et ajouter le contenu ci dessous  

```
[Variables]
gcode_offsets = {'x': None, 'y': None, 'z': 0.0}
```
