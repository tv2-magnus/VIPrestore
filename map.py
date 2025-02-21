import sys
from pyvis.network import Network
from PyQt6 import QtWidgets
import json

def create_network_map(res_data, parent_widget=None, endpoint_map=None, services_data=None):
    """
    Generates a Pyvis network graph with meaningful node labels and tooltips.
    
    Args:
        res_data (dict): Network path data containing nodes and edges.
        parent_widget (QWidget): Parent widget for error messages.
        endpoint_map (dict): Mapping of device IDs to user-friendly labels.
        services_data (dict): Additional service details for tooltips.
    """
    net = Network(notebook=False, directed=True, height="750px", width="100%")
    net.set_edge_smooth('dynamic')
    net.options.physics.enabled = False  # Fixed layout

    node_positions = {}  # Stores assigned positions: {node_id: (x, y)}
    added_nodes = set()  # Track added nodes to prevent duplicates

    consolidated_nodes = set()  # Track sender/receiver nodes
    edge_groups = {}  # {from_node: [(to_node, edge_id, color)]}

    def get_label(node_id):
        """Returns a user-friendly label for a given node ID."""
        return endpoint_map.get(node_id, node_id) if endpoint_map else node_id

    def get_tooltip(node_id):
        """Generates a tooltip for the given node with extra service details."""
        if not services_data or node_id not in services_data:
            return f"ID: {node_id}"

        service = services_data[node_id]
        tooltip = f"ID: {node_id}"

        # Add known attributes
        tooltip += f"<br><b>Label:</b> {get_label(node_id)}"
        tooltip += f"<br><b>Profile:</b> {service.get('profile_name', 'N/A')}"
        tooltip += f"<br><b>Created By:</b> {service.get('createdBy', 'N/A')}"
        tooltip += f"<br><b>Start:</b> {service.get('start', 'N/A')}"
        tooltip += f"<br><b>End:</b> {service.get('end', 'N/A')}"
        tooltip += f"<br><b>Allocation State:</b> {service.get('allocationState', 'N/A')}"

        return tooltip

    def register_edge(from_node, to_node, edge_id, color):
        """Handles edges while consolidating sender/receiver nodes."""
        if from_node not in edge_groups:
            edge_groups[from_node] = []
        edge_groups[from_node].append((to_node, edge_id, color))

    def add_path_nodes(edges, color, y_offset, path_type):
        """Processes path edges while keeping sender/receiver properly spaced."""
        if not edges:
            return

        spacing = 200
        x_offset = 100  # Move sender closer
        receiver_x_offset = 150  # Dynamically adjust receiver position

        sender_node = edges[0]["fromNode"]
        receiver_node = edges[-1]["toNode"]

        consolidated_nodes.add(sender_node)
        consolidated_nodes.add(receiver_node)

        # Ensure sender node is slightly closer to first node
        if sender_node not in added_nodes:
            node_positions[sender_node] = (-x_offset, 0)
            net.add_node(
                sender_node,
                label=get_label(sender_node),
                title=get_tooltip(sender_node),
                x=str(-x_offset),
                y="0",
                physics=False
            )
            added_nodes.add(sender_node)

        x = 0  # Start position for first path node
        last_x_main = last_x_spare = None  # Track final positions of main and spare paths

        # Process path nodes
        for i, edge in enumerate(edges):
            from_node = edge.get("fromNode")
            to_node = edge.get("toNode")
            edge_id = edge.get("id")

            is_sender = from_node == sender_node
            is_receiver = to_node == receiver_node

            if i == 0:
                y = -100 if path_type == "main" else 100
            elif is_receiver:
                y = 0
            else:
                y = y_offset

            # Add from_node if not already placed
            if from_node not in added_nodes:
                node_positions[from_node] = (x, y)
                net.add_node(
                    from_node,
                    label=get_label(from_node),
                    title=get_tooltip(from_node),
                    x=str(x),
                    y=str(y),
                    physics=False
                )
                added_nodes.add(from_node)

            x += spacing  # Keep spacing uniform

            # Store last node positions to determine receiver alignment
            if is_receiver:
                if path_type == "main":
                    last_x_main = x - spacing
                else:
                    last_x_spare = x - spacing

            # Add to_node if not already placed
            if to_node not in added_nodes:
                y = 0 if is_receiver else y_offset
                node_positions[to_node] = (x, y)
                net.add_node(
                    to_node,
                    label=get_label(to_node),
                    title=get_tooltip(to_node),
                    x=str(x),
                    y=str(y),
                    physics=False
                )
                added_nodes.add(to_node)

            # Register edges for later processing
            register_edge(from_node, to_node, edge_id, color)

        return last_x_main, last_x_spare  # Return last node positions for receiver placement

    try:
        paths = res_data.get("paths", [])
        last_x_main = last_x_spare = None  # Track last node positions

        for path_data in paths:
            main_path = path_data.get("path", {}).get("main", {})
            spare_path = path_data.get("path", {}).get("spare", {})

            main_edges = main_path.get("edges", []) if main_path else []
            spare_edges = spare_path.get("edges", []) if spare_path else []

            # Get last node x-coordinates for proper receiver alignment
            last_x_main, _ = add_path_nodes(main_edges, "blue", -200, "main")  # Main path (above sender)
            _, last_x_spare = add_path_nodes(spare_edges, "orange", 200, "spare")  # Spare path (below sender)

        # Adjust receiver node to be centered between last nodes
        if last_x_main is not None and last_x_spare is not None:
            receiver_x = (last_x_main + last_x_spare) / 2  # Midpoint of last nodes
        else:
            receiver_x = max(last_x_main or 0, last_x_spare or 0)  # Fallback

        receiver_node = next(iter(consolidated_nodes - {paths[0]["path"]["main"]["edges"][0]["fromNode"]}))  # Get receiver ID
        if receiver_node not in added_nodes:
            node_positions[receiver_node] = (receiver_x, 0)
            net.add_node(
                receiver_node,
                label=get_label(receiver_node),
                title=get_tooltip(receiver_node),
                x=str(receiver_x),
                y="0",
                physics=False
            )
            added_nodes.add(receiver_node)

        # --- Create the edges after processing all nodes ---
        for from_node, edges in edge_groups.items():
            for to_node, edge_id, color in edges:
                net.add_edge(from_node, to_node, title=edge_id, color=color)

    except Exception as e:
        if parent_widget:
            QtWidgets.QMessageBox.critical(parent_widget, "Map Generation Error", str(e))
        return ""

    return net.generate_html(notebook=False)
