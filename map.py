import logging
from PyQt6 import QtWidgets
from map_view import NetworkMapView

logger = logging.getLogger(__name__)

def create_network_map(res_data, parent_widget=None, endpoint_map=None, services_data=None):
    """
    Generates a QGraphicsView-based network graph with meaningful node labels and tooltips.
    
    Args:
        res_data (dict): Network path data containing nodes and edges.
        parent_widget (QWidget): Parent widget for error messages.
        endpoint_map (dict): Mapping of device IDs to user-friendly labels.
        services_data (dict): Additional service details for tooltips.
        
    Returns:
        NetworkMapView: A QGraphicsView widget containing the network map
    """
    logger.debug("Entering create_network_map with data of type: %s", type(res_data))
    
    # Create the map view
    map_view = NetworkMapView()
    
    # Error handling for invalid input data
    if not isinstance(res_data, dict):
        error_msg = f"res_data must be a dict, got {type(res_data).__name__}"
        logger.error(error_msg)
        if parent_widget:
            QtWidgets.QMessageBox.critical(parent_widget, "Map Generation Error", error_msg)
        return map_view
    
    # Check if the data structure contains the expected fields
    if "paths" not in res_data:
        error_msg = "Missing 'paths' field in res_data"
        logger.error(error_msg)
        if parent_widget:
            QtWidgets.QMessageBox.critical(parent_widget, "Map Generation Error", error_msg)
        return map_view
    
    paths = res_data.get("paths", [])
    if not paths:
        warning_msg = "No paths found in res_data"
        logger.warning(warning_msg)
        if parent_widget:
            QtWidgets.QMessageBox.warning(parent_widget, "Map Generation Warning", warning_msg)
        return map_view
    
    # Track nodes that have been added to avoid duplicates
    added_nodes = set()
    node_positions = {}  # {node_id: (x, y)}
    consolidated_nodes = set()
    edge_groups = {}     # {from_node: [(to_node, edge_id, color)]}

    def get_label(node_id):
        """Returns a user-friendly label for a given node ID."""
        if not node_id:
            logger.warning("Empty node_id passed to get_label")
            return "Unknown"
        return endpoint_map.get(node_id, node_id) if endpoint_map else node_id

    def get_tooltip(node_id):
        """Generates a tooltip for the given node with extra service details."""
        if not node_id:
            logger.warning("Empty node_id passed to get_tooltip")
            return "ID: Unknown"
            
        if not services_data or node_id not in services_data:
            return f"ID: {node_id}"

        try:
            service = services_data[node_id]
            tooltip = f"ID: {node_id}\n"
            tooltip += f"Label: {get_label(node_id)}\n"
            tooltip += f"Profile: {service.get('profile_name', 'N/A')}\n"
            tooltip += f"Created By: {service.get('createdBy', 'N/A')}\n"
            tooltip += f"Start: {service.get('start', 'N/A')}\n"
            tooltip += f"End: {service.get('end', 'N/A')}\n"
            tooltip += f"Allocation State: {service.get('allocationState', 'N/A')}"
            return tooltip
        except Exception as e:
            logger.error("Error generating tooltip for node %s: %s", node_id, str(e))
            return f"ID: {node_id} (Error: Could not generate complete tooltip)"

    def register_edge(from_node, to_node, edge_id, color):
        """Handles edges while consolidating sender/receiver nodes."""
        if not from_node or not to_node:
            logger.warning("Skipping edge with missing nodes: from=%s, to=%s", from_node, to_node)
            return
            
        if from_node not in edge_groups:
            edge_groups[from_node] = []
        edge_groups[from_node].append((to_node, edge_id, color))

    def add_path_nodes(edges, color, y_offset, path_type):
        """Processes path edges while keeping sender/receiver properly spaced."""
        if not edges:
            logger.debug("No edges provided for %s path", path_type)
            return None, None

        # Validate edges structure
        if not isinstance(edges, list):
            logger.error("Expected edges to be a list, got %s", type(edges))
            return None, None
            
        # Check if first edge has required fields
        if not edges[0].get("fromNode"):
            logger.warning("First edge in %s path is missing fromNode field", path_type)
            return None, None
            
        # Check if last edge has required fields
        if not edges[-1].get("toNode"):
            logger.warning("Last edge in %s path is missing toNode field", path_type)
            return None, None

        spacing = 200
        x_offset = 100
        sender_node = edges[0].get("fromNode", "")
        receiver_node = edges[-1].get("toNode", "")

        logger.debug("Processing %s path: sender=%s, receiver=%s, edge_count=%d", 
                    path_type, sender_node, receiver_node, len(edges))

        consolidated_nodes.add(sender_node)
        consolidated_nodes.add(receiver_node)

        # Ensure sender node is placed if not already
        if sender_node and sender_node not in added_nodes:
            node_positions[sender_node] = (-x_offset, 0)
            service_data = services_data.get(sender_node) if services_data else None
            map_view.add_node(
                sender_node,
                get_label(sender_node),
                -x_offset,
                0,
                get_tooltip(sender_node),
                service_data
            )
            added_nodes.add(sender_node)

        x = 0  # Start position for first path node
        last_x_main = last_x_spare = None

        # Process each edge in the path
        for i, edge in enumerate(edges):
            from_node = edge.get("fromNode", "")
            to_node = edge.get("toNode", "")
            edge_id = edge.get("id", "")
            
            if not from_node or not to_node:
                logger.warning("Edge %d in %s path has missing node(s): from=%s, to=%s", 
                              i, path_type, from_node, to_node)
                continue

            is_receiver = (to_node == receiver_node)

            if i == 0:
                # Shift the first edge's Y if it's main/spare
                y = -100 if path_type == "main" else 100
            elif is_receiver:
                y = 0
            else:
                y = y_offset

            # Add from_node
            if from_node and from_node not in added_nodes:
                node_positions[from_node] = (x, y)
                try:
                    service_data = services_data.get(from_node) if services_data else None
                    map_view.add_node(
                        from_node,
                        get_label(from_node),
                        x,
                        y,
                        get_tooltip(from_node),
                        service_data
                    )
                    added_nodes.add(from_node)
                except Exception as e:
                    logger.error("Failed to add node %s: %s", from_node, str(e))

            x += spacing

            # Track final x-positions for main/spare
            if is_receiver:
                if path_type == "main":
                    last_x_main = x - spacing
                else:
                    last_x_spare = x - spacing

            # Add to_node
            if to_node and to_node not in added_nodes:
                y = 0 if is_receiver else y_offset
                node_positions[to_node] = (x, y)
                try:
                    service_data = services_data.get(to_node) if services_data else None
                    map_view.add_node(
                        to_node,
                        get_label(to_node),
                        x,
                        y,
                        get_tooltip(to_node),
                        service_data
                    )
                    added_nodes.add(to_node)
                except Exception as e:
                    logger.error("Failed to add node %s: %s", to_node, str(e))

            # Register the edge for later creation
            register_edge(from_node, to_node, edge_id, color)

        return last_x_main, last_x_spare

    try:
        last_main_positions = []
        last_spare_positions = []

        for i, path_obj in enumerate(paths):
            logger.debug("Processing path %d of %d", i+1, len(paths))
            
            if "path" not in path_obj:
                logger.warning("Path object %d is missing 'path' field, skipping", i+1)
                continue

            main_data = path_obj["path"].get("main", {})
            spare_data = path_obj["path"].get("spare", {})

            if not main_data and not spare_data:
                logger.warning("Path object %d has neither main nor spare data, skipping", i+1)
                continue

            main_edges = main_data.get("edges", [])
            spare_edges = spare_data.get("edges", [])

            logger.debug("Path %d: main_edges=%d, spare_edges=%d", 
                        i+1, len(main_edges), len(spare_edges))

            main_last_x, _ = add_path_nodes(main_edges, "blue", -200, "main")
            _, spare_last_x = add_path_nodes(spare_edges, "orange", 200, "spare")
            
            if main_last_x is not None:
                last_main_positions.append(main_last_x)
            if spare_last_x is not None:
                last_spare_positions.append(spare_last_x)

        # Now create edges
        edge_count = 0
        for from_node, edges in edge_groups.items():
            for (to_node, edge_id, color) in edges:
                try:
                    # For edge service data, use the same as the source node
                    service_data = services_data.get(from_node) if services_data else None
                    map_view.add_edge(from_node, to_node, edge_id, color, service_data)
                    edge_count += 1
                except Exception as e:
                    logger.error("Failed to add edge from %s to %s: %s", from_node, to_node, str(e))
                    
        logger.debug("Successfully added %d nodes and %d edges to the map", len(added_nodes), edge_count)
        
        # Fit content to view
        map_view.fit_content()
        
        return map_view

    except Exception as e:
        error_msg = f"An unexpected exception occurred in create_network_map: {str(e)}"
        logger.exception(error_msg)
        if parent_widget:
            QtWidgets.QMessageBox.critical(parent_widget, "Map Generation Error", error_msg)
        return map_view