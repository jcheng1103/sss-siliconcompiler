import pandas
import os
from siliconcompiler import units
from siliconcompiler import Schema


def make_metric_dataframe(chip):
    """
    Returns a pandas dataframe to display in the data metrics table. All nodes
    (steps and indices) are included on the x-axis while the metrics tracked
    are on the y-axis. The y-axis row headers are in the form of a tuple where
    the first element is the metric tracked and the second element is the unit.

    Args:
        chip (Chip) : the chip object that contains the schema read from

    Example:
        >>> make_metric_dataframe(chip)
        returns pandas dataframe of tracked metrics
    """

    # from siliconcompiler/siliconcompiler/core.py, "summary" function
    flow = chip.get('option', 'flow')
    steplist = chip.list_steps()

    # only report tool based steps functions
    for step in steplist.copy():
        tool, task = chip._get_tool_task(step, '0', flow=flow)
        if chip._is_builtin(tool, task):
            index = steplist.index(step)
            del steplist[index]

    # Collections for data
    nodes = []
    metrics = {}
    metrics_unit = {}

    # Build ordered list of nodes in flowgraph
    for step in steplist:
        for index in chip.getkeys('flowgraph', flow, step):
            nodes.append((step, index))
            metrics[step, index] = {}

    # Gather data and determine which metrics to show
    # We show a metric if:
    # - it is not in ['option', 'metricoff'] -AND-
    # - at least one step in the steplist has a non-zero weight for the metric
    #  -OR -
    #   at least one step in the steplist set a value for it
    metrics_to_show = []
    for metric in chip.getkeys('metric'):
        if metric in chip.get('option', 'metricoff'):
            continue

        # Get the unit associated with the metric
        metric_unit = None
        if chip.schema._has_field('metric', metric, 'unit'):
            metric_unit = chip.get('metric', metric, field='unit')

        show_metric = False
        for step, index in nodes:
            if metric in chip.getkeys('flowgraph',
                                      flow,
                                      step,
                                      index,
                                      'weight')\
               and chip.get('flowgraph', flow, step, index, 'weight', metric):
                show_metric = True

            value = chip.get('metric', metric, step=step, index=index)
            if value is not None:
                show_metric = True
            tool, task = chip._get_tool_task(step, index, flow=flow)

            if value is not None:
                if metric == 'memory':
                    value = units.format_binary(value, metric_unit)
                elif metric in ['exetime', 'tasktime']:
                    metric_unit = None
                    value = units.format_time(value)
                else:
                    value = units.format_si(value, metric_unit)

            metrics[step, index][metric] = str(value)

        if show_metric:
            metrics_to_show.append(metric)
            metrics_unit[metric] = metric_unit if metric_unit else ''

    # converts from 2d dictionary to pandas DataFrame, transposes so
    # orientation is correct, and filters based on the metrics we track
    data = (pandas.DataFrame.from_dict(metrics, orient='index').transpose())
    data = data.loc[metrics_to_show]
    # include metrics_unit
    data.index = data.index.map(lambda x: (x, metrics_unit[x]))
    return data


def get_flowgraph_nodes(chip, step, index):
    """
    Returns a dictionary to display in the data metrics table. One node
    (step and index) is included on the x-axis while all the metrics tracked
    are on the y-axis.

    Args:
        chip (Chip) : the chip object that contains the schema read from
        step (string) : step of node
        index (string) : index of node

    Example:
        >>> get_flowgraph_nodes(chip, [(import, 0), (syn, 0)])
        returns pandas dataframe of tracked metrics
    """
    nodes = {}
    for key in chip.getkeys('record'):
        nodes[key] = chip.get('record', key, step=step, index=index)
    return nodes


def get_flowgraph_edges(chip):
    """
    Returns a dicitionary where each key is one node, a tuple in the form
    (step, index) and the value of each key is a list of tuples in the form
    (step, index). The value of each key represents all the nodes that is a
    prerequisite to the key node.

    Args:
        chip (Chip) : the chip object that contains the schema read from

    Example:
        >>> get_flowgraph_edges(chip)
        returns dictionary where the values of the keys are the edges
    """
    flowgraph_edges = {}
    flow = chip.get('option', 'flow')
    for step in chip.getkeys('flowgraph', flow):
        for index in chip.getkeys('flowgraph', flow, step):
            flowgraph_edges[step, index] = []
            for in_step, in_index in chip.get('flowgraph',
                                              flow,
                                              step,
                                              index,
                                              'input'):
                flowgraph_edges[step, index].append((in_step, in_index))
    return flowgraph_edges


def make_manifest_helper(manifest_subsect, modified_manifest_subsect):
    """
    function is a helper function to make_manifest. It mutates the input json.

    Args:
        manifest_subsect (dict) : represents a subset of the original manifest
        modified_manifest_subsect (dict) : represents a subset of the original
                                           manifest, modified for readability

    Example:
        >>> make_manifest_helper(manifest_subsection, {})
        mutates second paramaeter to remove simplify leaf nodes and remove
        'default' nodes
    """
    if Schema._is_leaf(manifest_subsect) and \
       'node' in manifest_subsect and \
       'default' in manifest_subsect['node'] and \
       'default' in manifest_subsect['node']['default'] and \
       'value' in manifest_subsect['node']['default']['default']:
        value = manifest_subsect['node']['default']['default']['value']
        modified_manifest_subsect['value'] = value
    else:
        for key in manifest_subsect:
            if key != 'default':
                modified_manifest_subsect[key] = {}
                make_manifest_helper(manifest_subsect[key],
                                     modified_manifest_subsect[key])
    return


def make_manifest(chip):
    """
    Returns a dictionary of dictionaries/json

    Args:
        chip(Chip) : the chip object that contains the schema read from

    Example:
        >>> make_manifest(chip)
        returns tree/json of manifest
    """
    # need to make deppcopy because of line 169 in schema_obj.py
    manifest = chip.schema.cfg
    modified_manifest = {}
    make_manifest_helper(manifest, modified_manifest)
    return modified_manifest


def get_flowgraph_path(chip, end_nodes=None):
    """
    Returns a dictionary where each key is a node that is part of the "winning"
    path. The value of each key is either None, "End Node", or "Start Node".
    None implies that that node is neither and end node nor a start node.

    Args:
        chip(Chip) : the chip object that contains the schema read from

    Example:
        >>> get_flowgraph_path(chip)
        returns the "winning" path for that job
    """
    steplist = chip.list_steps()
    flow = chip.get('option', 'flow')
    selected_nodes = set()
    to_search = []
    # Start search with any successful leaf nodes.
    if end_nodes is None:
        end_nodes = chip._get_flowgraph_exit_nodes(flow=flow,
                                                   steplist=steplist)
    for node in end_nodes:
        selected_nodes.add(node)
        to_search.append(node)
    # Search backwards, saving anything that was selected by leaf nodes.
    while len(to_search) > 0:
        node = to_search.pop(-1)
        input_nodes = chip.get('flowgraph', flow, *node, 'select')
        for selected in input_nodes:
            if selected not in selected_nodes:
                selected_nodes.add(selected)
                to_search.append(selected)
    return selected_nodes


def search_manifest_keys(manifest, key):
    """
    function is a recursive helper to search_manifest, more info there

    Args:
        manifest(dictionary) : a dicitionary representing the manifest
        key(string) : searches all keys for partial matches on this string
    """
    filtered_manifest = {}
    for dict_key in manifest:
        if key in dict_key:
            filtered_manifest[dict_key] = manifest[dict_key]
        elif isinstance(manifest[dict_key], dict):
            result = search_manifest_keys(manifest[dict_key], key)
            if result:  # result is non-empty
                filtered_manifest[dict_key] = result
    return filtered_manifest


def search_manifest_values(manifest, value):
    """
    function is a recursive helper to search_manifest, more info there

    Args:
        manifest(dictionary) : a dicitionary representing the manifest
        value(string) : searches all values for partial matches on this string
    """
    filtered_manifest = {}
    for key in manifest:
        if isinstance(manifest[key], dict):
            result = search_manifest_values(manifest[key], value)
            if result:  # result is non-empty
                filtered_manifest[key] = result
        elif isinstance(manifest[key], str) and value in manifest[key]:
            filtered_manifest[key] = manifest[key]
    return filtered_manifest


def search_manifest(manifest, key_search=None, value_search=None):
    """
    Returns the same structure as make_manifest, but it is filtered by partial
    matches by keys or values. If both key_search and value_search are None,
    the original manifest is returned.

    Args:
        manifest(dictionary) : a dicitionary representing the manifest
        key_search(string) : searches all keys for partial matches on this
        string value_search(string) : searches all values for partial matches
        on this string.

    Example:
        >>> search_manifest(jsonDict, key_search='input', value_search='v')
        returns a filtered version of jsonDict where each path contains at
        least one key that contains the substring input and has values that
        contain v.
    """
    return_manifest = manifest
    if key_search:
        return_manifest = search_manifest_keys(return_manifest, key_search)
    if value_search:
        return_manifest = search_manifest_values(return_manifest, value_search)
    return return_manifest


def get_total_manifest_parameter_count(manifest):
    """
    Returns (int) the number of folders and files

    Args:
        manifest(dictionary) : a dicitionary representing the manifest
        acc(int) : an accumulator of the current number of folders and files
    """
    acc = len(manifest)
    for dictKeys in manifest:
        if isinstance(manifest[dictKeys], dict):
            acc += get_total_manifest_parameter_count(manifest[dictKeys])
    return acc


def get_logs_and_reports(chip, step, index):
    """
    returns a list of 3-tuple that contain the path name of how to get to that
    folder, the subfolders of that directory, and it's files. The list is
    ordered by layer of directory.

    Args:
        chip (Chip) : the chip object that contains the schema read from
        step (string) : step of node
        index (string) : index of node
    """
    # could combine filters, but slighlty more efficient to seperate them
    folder_filters = {"inputs",
                      "reports",
                      "outputs"}
    file_filters = {f'{step}.log',
                    f'{step}.errors',
                    f'{step}.warnings'}
    filtered_logs_and_reports = []
    all_paths = os.walk(chip._getworkdir(step=step, index=index))
    for path_name, folders, files in all_paths:
        for filter in folder_filters:
            if filter in path_name or filter in folders:
                filtered_logs_and_reports.append((path_name,
                                                  folders,
                                                  files))
                break
    # the first layer of all of these folders and files needs to undergo
    # further filtering
    path_name, folders, files = filtered_logs_and_reports[0]
    for folder in folders:
        if folder not in folder_filters:
            folders.remove(folder)
    for file in files:
        if file not in file_filters:
            files.remove(file)
    return filtered_logs_and_reports
