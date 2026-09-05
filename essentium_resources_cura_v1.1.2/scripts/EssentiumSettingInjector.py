# Written by Drew Marks (drew.marks@essentium.com)
# Updated by Jack Rentz (jack.rentz@essentium.com)

import traceback
import os.path
import json
from ..Script import Script
from cura.CuraApplication import CuraApplication
from UM.Resources import Resources


class EssentiumSettingInjector(Script):
    """
    """

    CONFIG_PATH = os.path.join(Resources.getStoragePath(Resources.Resources), "scripts",
                               "EssentiumSettingInjector.cfg.json")

    DEFAULT_MATERIAL_NOZZLE_MAP = {
        "material_map": {
            "HTN": "HTN",
            "PCTG": "PCTG",
            "PET CF": "PET_CF",
            "TPU 74D": "TPU_74D",
            "9085": "9085",
            "PLA": "PLA",
            "PA CF": "PA_CF",
            "HTN CF": "HTN_CF",
            "ABS": "ABS",
            "S10": "S10",
            "VXL 90": "VXL 90",
            "9085 Support": "9085 Support",
            "Altitude": "Altitude",
            "PPSCF": "PPSCF",
            "PEEK": "PEEK",
            "HIPS": "HIPS",
            "TPU 95A": "TPU_95A",
            "TPU 58D AS": "TPU_58D_AS"
        },
        "nozzle_map": {
            "GenV 0.8mm": "GEN_V_0.8",
            "GenV 0.4mm": "GEN_V_0.4",
            "GenVI 0.8mm": "GEN_VI_0.8",
            "GenVI 0.4mm": "GEN_VI_0.4"
        },
        "default_nozzle": "V"
    }

    SETTINGS_INDENT = '    '

    IGNORED_SETTINGS = ['machine_start_gcode', 'machine_end_gcode']

    def __init__(self):
        super().__init__()

    def getSettingDataString(self):
        return """{
            "name": "Essentium Setting Injector",
            "key": "EssentiumSettingInjector",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "insert_header":
                {
                    "label": "Insert Setup Header",
                    "description": "When enabled, a specially formatted header for the material management system will be inserted at the first line of the output gcode.",
                    "type": "bool",
                    "default_value": true
                },
                "insert_all_settings":
                {
                    "label": "Insert All Slicer Settings",
                    "description": "When enabled, all editable cura settings will be inserted at the very beginning of the gcode. These settings will appear after the header, if it is enabled.",
                    "type": "bool",
                    "default_value": true
                }
            }
        }"""

    def get_all_child_settings(self, stack, parent, indent):
        if len(stack.getSettingDefinition(parent).children) < 1:
            return {}

        children_dictionary = {}
        for child in stack.getSettingDefinition(parent).children:
            if child.key not in self.IGNORED_SETTINGS:
                children_dictionary[indent + stack.getProperty(child.key, "label")] = child.key
            children_dictionary.update(self.get_all_child_settings(stack, child.key, indent + self.SETTINGS_INDENT))

        return children_dictionary

    def get_settings_dictionary(self, stack):
        settings_dictionary = {}
        for category in stack.definition.findDefinitions(type="category"):
            category_key = stack.getProperty(category.key, "label")
            category_dictionary = self.get_all_child_settings(stack, category.key, self.SETTINGS_INDENT)
            settings_dictionary[category_key] = category_dictionary

        return settings_dictionary

    def get_extruder_data(self, extruder_manager, key):
        data = extruder_manager.getInstanceExtruderValues(key)
        if data and len(data) > 0:
            return ', '.join([str(item) for item in data])

        return 'Error: setting not found'

    def generate_setting_data(self, instance):

        settings_str = ';--------Essentium Cura Settings--------\n'
        for category, settings_dict in self.get_settings_dictionary(instance.getGlobalContainerStack()).items():
            settings_str += ';---' + category + '---\n'
            for name, key in settings_dict.items():
                settings_str += ';' + name + ': ' + self.get_extruder_data(instance.getExtruderManager(), key) + '\n'

        return settings_str

    def map_heads_data(self, material, nozzle, extruder):
        try:
            file_obj = open(self.CONFIG_PATH, "r")
            maps = json.loads(file_obj.read())
            file_obj.close()
        except FileNotFoundError:
            maps = self.DEFAULT_MATERIAL_NOZZLE_MAP

        msg = 'ERROR - No mapping found'

        if material in maps['material_map']:
            material = maps['material_map'][material]
        else:
            material = msg

        if not nozzle:
            nozzle = 'GEN_' + maps["default_nozzle"] + '_' + str(extruder.getProperty('machine_nozzle_size', "value"))
        elif nozzle in maps['nozzle_map']:
            nozzle = maps['nozzle_map'][nozzle]
        elif nozzle.startswith("Gen") and nozzle.endswith("mm"):
            nozzle = 'GEN_' + nozzle[3:-2].upper().replace(" ", "_")
        else:
            nozzle = msg

        return {"Material": material, "Nozzle": nozzle}

    def get_heads_data(self, extruder_manager):
        heads_data = []
        for e in extruder_manager.getActiveExtruderStacks():
            data = e.material.getMetaData()
            mat = data.get("name", None)
            noz = data.get("variant_name", None)
            heads_data.append(self.map_heads_data(mat, noz, e))

        return heads_data

    def get_header_data(self, extruder_manager):
        chamber_temp = extruder_manager.getResolveOrValue('build_volume_temperature')
        bed_temp = extruder_manager.getResolveOrValue('material_bed_temperature')
        heads_data = self.get_heads_data(extruder_manager)

        return chamber_temp, bed_temp, heads_data

    def generate_header_data(self, extruders):
        chamber_temp, bed_temp, heads_data = self.get_header_data(extruders)
        header_json = {"Chamber": {"PreHeatTemp": chamber_temp}, "Bed": {"PreHeatTemp": bed_temp}, "Heads": heads_data}

        header_str = ';START MACHINE SETUP\n'
        for line in map(lambda l: ';{}\n'.format(l), json.dumps(header_json, indent=4).split('\n')):
            header_str += line
        header_str += ';END MACHINE SETUP\n'

        return header_str

    def execute(self, data):
        insert_header = self.getSettingValueByKey("insert_header")
        insert_all_settings = self.getSettingValueByKey("insert_all_settings")
        if not (insert_header or insert_all_settings):
            return data

        instance = CuraApplication.getInstance()
        lines_to_insert = ''

        try:
            if insert_header:
                lines_to_insert += self.generate_header_data(instance.getExtruderManager())
        except Exception:
            lines_to_insert += ';-----Error trying to generate material management header-----'
            for line in map(lambda l: ';{}\n'.format(l), traceback.format_exc().split('\n')):
                lines_to_insert += line

        try:
            if insert_all_settings:
                lines_to_insert += self.generate_setting_data(instance)
        except Exception:
            lines_to_insert += ';-----Error trying to extract settings data from Cura-----'
            for line in map(lambda l: ';{}\n'.format(l), traceback.format_exc().split('\n')):
                lines_to_insert += line

        layer = lines_to_insert + data[0]
        data[0] = layer

        return data
