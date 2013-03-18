# Common definitions for 'loc2yaml' and 'loctrans' tools
# https://github.com/sergeuz/locode
#
# This file is subject to the terms and conditions defined in LICENSE file,
# which is part of this source code package.

import yaml, shutil, os, sys
from collections import OrderedDict

# Placeholder region code used when particular location has no region specified.
# Shouldn't match any of subdivision codes defined by ISO 3166-2
UNKNOWN_REGION_CODE = ".NONE"
DEFAULT_OUTPUT_BASENAME = "country"
PARSER_HINT_TAG = "flags"
TODO_MARKER = "(TODO)"
PROJECT_HOMEPAGE = "https://github.com/sergeuz/locode"
VERSION_STRING = "0.1.0"

# Supported parser hints
PARSER_HINT_PRESERVE = "preserve"
PARSER_HINT_ODD = "odd" # Not recognized actually, see "Document structure"

# Global module settings
quiet = False
verbose = False


def print_q(*objs):
    if not quiet:
        print(*objs)


def print_v(*objs):
    if verbose:
        print_q(*objs)


def simplify_str(s):
    return ' '.join(s.split())


def is_upper_str(s):
    for c in s:
        if c.isalpha() and not c.istitle():
            return False
    return True


def transact_copy(src_dir, dest_dir, replace=None):
    files = []
    # At first step checking if we actually can write all our destination files
    for name in os.listdir(src_dir):
        src_file = os.path.abspath(src_dir + '/' + name)
        if not os.path.isfile(src_file):
            continue
        dest_file = os.path.abspath(dest_dir + '/' + name)
        if not os.path.exists(dest_file) or os.path.isfile(dest_file) and os.access(dest_file, os.W_OK):
            files.append((src_file, dest_file))
        else:
            raise RuntimeError("Unable to write to file: {}".format(dest_file))
    # Copying files
    for src_file, dest_file in files:
        if replace != None:
            if os.path.exists(dest_file):
                if replace:
                    print_q("Replacing file:", dest_file)
                else:
                    print_q("Updating file:", dest_file) # Actually we always overwrite files
            else:
                print_q("Creating file:", dest_file)
        else:
            print_q("Saving file:", dest_file) # Generic message
        shutil.copyfile(src_file, dest_file)


def parse_yml_file(file_name, yml_dest, ctry_codes):
    print_q("Loading file:", file_name)
    f = open(file_name, 'r')
    yml_src = yaml.safe_load(f)
    f.close()

    if "country" not in yml_src:
        sys.stderr.write("Warning: No country data found, skipping file\n")
        return

    # Checking if all codes are provided in upper case. Helps mostly with loc2yaml
    # debugging when certain unquoted node names, such as 'NO' (Norway), are being
    # converted to other Python types by pyyaml's safe_load() parser, rather than
    # being represented as strings
    src_ctry_root = yml_src["country"]
    for ctry_code, src_ctry in src_ctry_root.items():
        if len(ctry_code) != 2:
            sys.stderr.write("Warning: Invalid country code: {}\n".format(ctry_code))
            continue
        if not is_upper_str(ctry_code):
            sys.stderr.write("Warning: Country code contains mixed case letters: {}\n".format(ctry_code))
        if "region" in src_ctry:
            for region_code, src_region in src_ctry["region"].items():
                if not is_upper_str(region_code):
                    sys.stderr.write("Warning: Region code contains mixed case letters: {}\n".format(region_code))
                if "city" in src_region:
                    for city_code in src_region["city"].keys():
                        if not is_upper_str(city_code):
                            sys.stderr.write("Warning: City code contains mixed case letters: {}\n".format(city_code))
    if ctry_codes:
        # Filtering content by country codes
        dest_ctry_root = yml_dest["country"]
        for ctry_code in src_ctry_root:
            if ctry_code in ctry_codes: # Upper-case expected
                dest_ctry_root.setdefault(ctry_code, {}).update(src_ctry_root[ctry_code])
            else:
                continue
    else:
        yml_dest.update(yml_src)


def arrange_yml_nodes(yml_node):
    if type(yml_node) != type({}):
        return yml_node;

    # Nodes to appear at first place
    head = ["name", "default", PARSER_HINT_TAG]
    # And ones to be placed at the end
    tail = ["region", "city", UNKNOWN_REGION_CODE]

    res = OrderedDict()
    for key in head:
        if key in yml_node:
            res[key] = arrange_yml_nodes(yml_node[key])
    for key, val in sorted(yml_node.items()): # Other nodes come in sorted order
        if key not in head and key not in tail:
            res[key] = arrange_yml_nodes(val)
    for key in tail:
        if key in yml_node:
            res[key] = arrange_yml_nodes(yml_node[key])

    return res


def write_yml_data(yml_root, stream):
    stream.write(yaml.safe_dump(arrange_yml_nodes(yml_root), # Order YAML nodes in specific manner
        allow_unicode=True, default_flow_style=False))


# Representer function for pyyaml used to dump OrderedDict objects. Basically a
# copy-paste of BaseRepresenter.represent_mapping() without using sort()
def represent_odict(dump, tag, mapping, flow_style = None):
    value = []
    node = yaml.MappingNode(tag, value, flow_style=flow_style)
    if dump.alias_key is not None:
        dump.represented_objects[dump.alias_key] = node
    best_style = True
    if hasattr(mapping, 'items'):
        mapping = mapping.items()
    for item_key, item_value in mapping:
        node_key = dump.represent_data(item_key)
        node_value = dump.represent_data(item_value)
        if not (isinstance(node_key, yaml.ScalarNode) and not node_key.style):
            best_style = False
        if not (isinstance(node_value, yaml.ScalarNode) and not node_value.style):
            best_style = False
        value.append((node_key, node_value))
    if flow_style is None:
        if dump.default_flow_style is not None:
            node.flow_style = dump.default_flow_style
        else:
            node.flow_style = best_style
    return node


if __name__ == "locode":
    # Installing our custom representer for OrderedDict objects
    yaml.SafeDumper.add_representer(OrderedDict,
        lambda dump, val: represent_odict(dump, "tag:yaml.org,2002:map", val))
