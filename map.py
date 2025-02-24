import logging
from pyvis.network import Network
from PyQt6 import QtWidgets

logger = logging.getLogger(__name__)

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

    node_positions = {}  # {node_id: (x, y)}
    added_nodes = set()
    consolidated_nodes = set()
    edge_groups = {}     # {from_node: [(to_node, edge_id, color)]}

    def get_label(node_id):
        """Returns a user-friendly label for a given node ID."""
        return endpoint_map.get(node_id, node_id) if endpoint_map else node_id

    def get_tooltip(node_id):
        """Generates a tooltip for the given node with extra service details."""
        if not services_data or node_id not in services_data:
            return f"ID: {node_id}"

        service = services_data[node_id]
        tooltip = f"ID: {node_id}"
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
            return None, None

        spacing = 200
        x_offset = 100
        sender_node = edges[0].get("fromNode", "")
        receiver_node = edges[-1].get("toNode", "")

        consolidated_nodes.add(sender_node)
        consolidated_nodes.add(receiver_node)

        # Ensure sender node is placed if not already
        if sender_node and sender_node not in added_nodes:
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
        last_x_main = last_x_spare = None

        # Process each edge in the path
        for i, edge in enumerate(edges):
            from_node = edge.get("fromNode", "")
            to_node   = edge.get("toNode", "")
            edge_id   = edge.get("id", "")

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
                net.add_node(
                    from_node,
                    label=get_label(from_node),
                    title=get_tooltip(from_node),
                    x=str(x),
                    y=str(y),
                    physics=False
                )
                added_nodes.add(from_node)

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
                net.add_node(
                    to_node,
                    label=get_label(to_node),
                    title=get_tooltip(to_node),
                    x=str(x),
                    y=str(y),
                    physics=False
                )
                added_nodes.add(to_node)

            # Register the edge for later creation
            register_edge(from_node, to_node, edge_id, color)

        return last_x_main, last_x_spare

    try:
        # Ensure 'res_data' is valid:
        if not isinstance(res_data, dict):
            msg = "res_data must be a dict"
            logger.error(msg)
            if parent_widget:
                QtWidgets.QMessageBox.critical(parent_widget, "Map Generation Error", msg)
            return " "

        paths = res_data.get("paths", [])
        if not paths:
            # If no paths, build minimal HTML so we don't return empty
            logger.debug("No paths in res_data; returning minimal HTML.")
            return _build_minimal_html("No path data found")

        last_main_positions = []
        last_spare_positions = []

        for path_obj in paths:
            if "path" not in path_obj:
                continue

            main_data = path_obj["path"].get("main", {})
            spare_data = path_obj["path"].get("spare", {})

            main_edges = main_data.get("edges", [])
            spare_edges = spare_data.get("edges", [])

            main_last_x, _ = add_path_nodes(main_edges, "blue", -200, "main")
            _, spare_last_x = add_path_nodes(spare_edges, "orange", 200, "spare")
            if main_last_x is not None:
                last_main_positions.append(main_last_x)
            if spare_last_x is not None:
                last_spare_positions.append(spare_last_x)

        # Attempt to compute a final x-position for the "receiver"
        if last_main_positions and last_spare_positions:
            receiver_x = (last_main_positions[-1] + last_spare_positions[-1]) / 2
        elif last_main_positions:
            receiver_x = last_main_positions[-1]
        elif last_spare_positions:
            receiver_x = last_spare_positions[-1]
        else:
            receiver_x = 0

        # If we do have a consolidated_nodes set, we might want to place the last receiver in center
        # But it's possible there's more than one. We'll pick one arbitrarily or skip.
        # Just skip if we can't identify a single "last" node:
        # (Optional, depends on your logic.)
        #
        # For example, if you want to place ANY node that isn't the first "sender" at receiver_x=0:
        #
        # all_senders = set()
        # for path_obj in paths:
        #     main = path_obj.get("path", {}).get("main", {}).get("edges", [])
        #     if main:
        #         all_senders.add(main[0].get("fromNode", ""))
        # potential_receivers = consolidated_nodes - all_senders
        # if len(potential_receivers) == 1:
        #     receiver_node = next(iter(potential_receivers))
        #     # Move it
        #     ...

        # Now create edges in PyVis
        for from_node, edges in edge_groups.items():
            for (to_node, edge_id, color) in edges:
                net.add_edge(from_node, to_node, title=edge_id, color=color)

        # All good — generate final HTML
        html_result = net.generate_html(notebook=False)
        if not html_result.strip():
            logger.debug("PyVis generate_html returned an empty string. Returning fallback HTML.")
            return _build_minimal_html("No rendered map data")

        return html_result

    except Exception as e:
        logger.exception("An exception occurred in create_network_map")
        if parent_widget:
            QtWidgets.QMessageBox.critical(parent_widget, "Map Generation Error", str(e))
        # Return a non-empty fallback so the caller doesn't treat this as "no HTML"
        return _build_minimal_html(f"Error: {e}")


def _build_minimal_html(message: str) -> str:
    """Builds a tiny fallback HTML snippet so we never return an empty or None."""
    return f"""
    <html>
    <head>
        <title>Network Map</title>
    </head>
    <body>
        <h2>{message}</h2>
    </body>
    </html>
    """
