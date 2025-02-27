from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsPathItem, QGraphicsRectItem, QToolTip, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath, QFont, QPainter
import logging
import math

logger = logging.getLogger(__name__)

class MapInfoPanel(QWidget):
    """Information panel for displaying details about selected map elements"""
    
    def __init__(self, parent=None):
        # Make this a proper dialog
        super().__init__(None)  # No parent - independent window
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(300)
        self.setWindowTitle("Network Element Details")
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Create title label
        self.titleLabel = QLabel("Device Information")
        self.titleLabel.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.titleLabel)
        
        # Create content area
        self.contentArea = QScrollArea()
        self.contentArea.setWidgetResizable(True)
        self.contentWidget = QWidget()
        self.contentLayout = QVBoxLayout(self.contentWidget)
        self.contentArea.setWidget(self.contentWidget)
        layout.addWidget(self.contentArea)
        
        # Add close button
        self.closeButton = QPushButton("Close")
        self.closeButton.clicked.connect(self.close)
        layout.addWidget(self.closeButton)
        
    def showNodeInfo(self, node_id, node_data):
        """Display information about a node"""
        self.titleLabel.setText(f"Device: {node_data.get('label', node_id)}")
        self._clearContent()
        
        # Add device information
        self._addInfoSection("Device ID", node_id)
        
        # Add device details if available
        if 'device_details' in node_data:
            details = node_data['device_details']
            
            if 'type' in details:
                self._addInfoSection("Device Type", details['type'])
            
            if 'vertexType' in details:
                self._addInfoSection("Interface Type", details['vertexType'])
                
            if 'codecFormat' in details:
                self._addInfoSection("Format", details['codecFormat'])
                
            # Add any other properties found
            for key, value in details.items():
                if key not in ['type', 'vertexType', 'codecFormat', 'descriptor'] and not isinstance(value, dict) and not isinstance(value, list):
                    self._addInfoSection(key, str(value))
        
        # Process service data
        if 'service_data' in node_data and node_data['service_data'] is not None:
            # Add service information
            service_data = node_data['service_data']
            self._addInfoSection("Service ID", service_data.get("serviceId", "N/A"))
            self._addInfoSection("Profile", service_data.get("profile_name", "N/A"))
            self._addInfoSection("Created By", service_data.get("createdBy", "N/A"))
            self._addInfoSection("Allocation State", service_data.get("allocationState", "N/A"))
            
            # Add timing information
            self._addInfoSection("Start Time", service_data.get("start", "N/A"))
            self._addInfoSection("End Time", service_data.get("end", "N/A"))
        
        self.adjustSize()
        self.show()
        self.raise_()  # Ensure window is on top
        self.activateWindow()  # Make sure it's active

    def showEvent(self, event):
        """Override to ensure proper focus when shown"""
        super().showEvent(event)
        self.activateWindow()
        self.raise_()

    def showEdgeInfo(self, edge_id, edge_data):
        """Display information about an edge"""
        self.titleLabel.setText(f"Connection: {edge_id}")
        self._clearContent()
        
        # Add connection type info
        if edge_data.get("color") == "blue":
            path_type = "Main Path"
        elif edge_data.get("color") == "orange":
            path_type = "Spare Path"
        else:
            path_type = "Connection"
            
        self._addInfoSection("Connection Type", path_type)
        self._addInfoSection("Connection ID", edge_id)
        
        # Check if service_data exists and is not None
        if 'service_data' in edge_data and edge_data['service_data'] is not None:
            # Add service information that's relevant to connections
            service_data = edge_data['service_data']
            self._addInfoSection("Service ID", service_data.get("serviceId", "N/A"))
            self._addInfoSection("Profile", service_data.get("profile_name", "N/A"))
        
        self.adjustSize()
        self.show()
    
    def _clearContent(self):
        """Clear the content area"""
        while self.contentLayout.count():
            item = self.contentLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _addInfoSection(self, title, value):
        """Add an information section with title and value"""
        section = QWidget()
        layout = QHBoxLayout(section)
        layout.setContentsMargins(0, 2, 0, 2)
        
        titleLabel = QLabel(f"{title}:")
        titleLabel.setStyleSheet("font-weight: bold;")
        layout.addWidget(titleLabel)
        
        valueLabel = QLabel(str(value))
        valueLabel.setWordWrap(True)
        layout.addWidget(valueLabel)
        
        self.contentLayout.addWidget(section)

class NetworkNode(QGraphicsEllipseItem):
    """Custom node for network visualization"""
    
    def __init__(self, node_id, label, x, y, tooltip="", service_data=None, parent=None):
        # Create a node with 30x30 size
        super().__init__(0, 0, 30, 30, parent)
        self.node_id = node_id
        self.label = label
        self.tooltip = tooltip
        self.service_data = service_data
        self.data = {'label': label, 'service_data': service_data}
        
        # Configure appearance
        self.setBrush(QBrush(QColor("#5DADE2")))
        self.setPen(QPen(QColor("#2874A6"), 2))
        
        # Set position
        self.setPos(x, y)
        
        # Add the label text
        self.text_item = QGraphicsTextItem(self)
        self.text_item.setPlainText(label)
        self.text_item.setPos(-self.text_item.boundingRect().width()/2 + 15, 35)
        
        # Make node selectable and movable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        
    def hoverEnterEvent(self, event):
        QToolTip.showText(event.screenPos(), self.tooltip)
        super().hoverEnterEvent(event)
        
    def itemChange(self, change, value):
        # Update connected edges when node moves
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            for edge in self.scene().items():
                if isinstance(edge, NetworkEdge) and (edge.source_node == self or edge.target_node == self):
                    edge.adjust()
        return super().itemChange(change, value)
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            # Tell the view to show info panel for this node
            if self.scene() and hasattr(self.scene().views()[0], 'showNodeInfo'):
                self.scene().views()[0].showNodeInfo(self.node_id, self.data)

class NetworkEdge(QGraphicsPathItem):
    """Custom edge for network visualization"""
    
    def __init__(self, source_node, target_node, edge_id="", color="blue", service_data=None, parent=None):
        super().__init__(parent)
        self.source_node = source_node
        self.target_node = target_node
        self.edge_id = edge_id
        self.service_data = service_data
        self.data = {'color': color, 'service_data': service_data}
        
        # Set appearance
        color = QColor(color)
        self.setPen(QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        
        # Set Z-value below nodes
        self.setZValue(-1)
        
        # Initialize path
        self.adjust()
        
        # Make edge selectable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        
    def adjust(self):
        """Update edge path based on connected nodes' positions"""
        if not self.source_node or not self.target_node:
            return
            
        # Get center points of source and target nodes
        source_pos = self.source_node.scenePos() + QPointF(15, 15)
        target_pos = self.target_node.scenePos() + QPointF(15, 15)
        
        # Create path
        path = QPainterPath()
        path.moveTo(source_pos)
        path.lineTo(target_pos)
        
        # Add arrow at target end
        angle = math.atan2(target_pos.y() - source_pos.y(), target_pos.x() - source_pos.x())
        arrow_size = 10
        arrow_p1 = target_pos + QPointF(math.sin(angle - math.pi/3) * arrow_size,
                                       math.cos(angle - math.pi/3) * arrow_size)
        arrow_p2 = target_pos + QPointF(math.sin(angle - math.pi + math.pi/3) * arrow_size,
                                       math.cos(angle - math.pi + math.pi/3) * arrow_size)
        path.lineTo(arrow_p1)
        path.moveTo(target_pos)
        path.lineTo(arrow_p2)
        
        self.setPath(path)
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            # Tell the view to show info panel for this edge
            if self.scene() and hasattr(self.scene().views()[0], 'showEdgeInfo'):
                self.scene().views()[0].showEdgeInfo(self.edge_id, self.data)

class NetworkMapView(QGraphicsView):
    """Custom QGraphicsView for network map visualization"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        
        # Configure view
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        
        # Add background
        self.setBackgroundBrush(QBrush(QColor("#F5F5F5")))
        
        # Create info panel
        self.info_panel = MapInfoPanel()
        
        # Track nodes and edges
        self.nodes = {}  # node_id -> NetworkNode
        self.edges = []  # list of NetworkEdge

    def fetch_device_details(self, node_id):
        """Fetch additional device details from the API if possible"""
        try:
            # If we have a client reference, use it to fetch device data
            if hasattr(self, 'client') and self.client:
                # For network elements
                if node_id.startswith('device'):
                    endpoint_data = self.client.get(f"/rest/v1/data/config/network/nGraphElements/{node_id}/value/**")
                    if endpoint_data and 'data' in endpoint_data:
                        return endpoint_data['data']['config']['network']['nGraphElements'][node_id]['value']
                
                # For external endpoints
                elif node_id.startswith('external'):
                    ext_data = self.client.get(f"/rest/v1/data/status/network/externalEndpoints/{node_id}/**")
                    if ext_data and 'data' in ext_data:
                        return ext_data['data']['status']['network']['externalEndpoints'][node_id]
        except Exception as e:
            logger.error(f"Error fetching device details: {e}")
        
        return None

    def closeEvent(self, event):
        """Ensure info panel is closed when view is closed"""
        if self.info_panel and self.info_panel.isVisible():
            self.info_panel.close()
        super().closeEvent(event)

    def add_node(self, node_id, label, x, y, tooltip="", service_data=None):
        """Add a node to the network map"""
        node = NetworkNode(node_id, label, x, y, tooltip, service_data)
        self.scene().addItem(node)
        self.nodes[node_id] = node
        return node
        
    def add_edge(self, source_id, target_id, edge_id="", color="blue", service_data=None):
        """Add an edge between two nodes"""
        if source_id not in self.nodes or target_id not in self.nodes:
            logger.warning(f"Cannot create edge: source or target not found ({source_id} -> {target_id})")
            return None
            
        source_node = self.nodes[source_id]
        target_node = self.nodes[target_id]
        
        edge = NetworkEdge(source_node, target_node, edge_id, color, service_data)
        self.scene().addItem(edge)
        self.edges.append(edge)
        return edge
    
    def showNodeInfo(self, node_id, node_data):
        """Show information panel for a node"""
        self.info_panel.showNodeInfo(node_id, node_data)
    
    def showEdgeInfo(self, edge_id, edge_data):
        """Show information panel for an edge"""
        self.info_panel.showEdgeInfo(edge_id, edge_data)
        
    def wheelEvent(self, event):
        """Handle zoom with mouse wheel"""
        zoom_factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(zoom_factor, zoom_factor)
        else:
            self.scale(1 / zoom_factor, 1 / zoom_factor)
            
    def fit_content(self):
        """Scale view to fit all content"""
        self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.scale(0.95, 0.95)  # Add a small margin