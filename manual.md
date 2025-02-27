# VIPrestore User Manual

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Getting Started](#getting-started)
4. [Main Interface](#main-interface)
5. [Working with Services](#working-with-services)
6. [Filtering Services](#filtering-services)
7. [Service Details](#service-details)
8. [Network Visualization](#network-visualization)
9. [Remote Systems Configuration](#remote-systems-configuration)
10. [Application Updates](#application-updates)
11. [Troubleshooting](#troubleshooting)
12. [Technical Reference](#technical-reference)

---

## Introduction

VIPrestore is a specialized client application designed for VideoIPath service management. It enables users to view, save, restore, and manage VideoIPath services across multiple systems. This tool is particularly useful for batch operations and service migration between environments.

### Key Features

* **Connect** to multiple VideoIPath systems
* **View and filter** services by various criteria
* **Save** selected services to JSON files
* **Restore** services from saved files
* **Cancel** services
* **View** detailed service information including network maps
* **Automatically check** for application updates

### System Requirements
* Windows computer
* Network connection to VideoIPath systems

---

## Installation

### Windows Installer
1. Download the latest installer from [GitHub Releases](https://github.com/magnusoverli/VIPrestore/releases/latest)
2. Run the installer and follow the prompts
3. The application will be installed to `C:\Program Files\VIPrestore` by default
4. Shortcuts will be created on your desktop and start menu

### First-Time Setup

On first launch, VIPrestore will create a configuration directory at:

* Windows: `%LOCALAPPDATA%\VIPrestore`
* macOS: `~/Library/Application Support/VIPrestore`
* Linux: `~/.config/VIPrestore`

This directory stores your remotesystems.json configuration and logs.

---

## Getting Started

### Connecting to a VideoIPath System

1. Launch VIPrestore
2. Click **File → Login** or press **Ctrl+L**
3. Select a remote system from the dropdown menu
4. Enter your VideoIPath username and password
5. Click **Login**

> **Note:** If connecting to a system with an invalid SSL certificate, you'll be prompted with a security warning. Only proceed if you understand the security implications.

### Connection Status

The connection status is displayed in the status bar at the bottom of the main window:

* **Grey**: Not connected
* **Green**: Connected via secure HTTPS with valid SSL
* **Orange**: Connected via HTTPS with invalid SSL (less secure)
* **Red**: Connected via unsecured HTTP (not recommended)

### Logging Out

* Click **File → Logout** or press **Ctrl+Shift+L**

---

## Main Interface

The VIPrestore interface consists of the following key areas:

### Menu Bar

* **File**: Login, logout, load/save services, exit
* **Tools**: Refresh services, edit systems, cancel services
* **Help**: About dialog, version information

### Service Table (Main Panel)

Displays all services from the connected VideoIPath system with the following columns:

* **Service ID**: Unique identifier for the service
* **Source**: Source endpoint
* **Destination**: Destination endpoint
* **Profile**: Service profile
* **Created By**: User who created the service
* **Start**: Service start time

### Service Details Panel (Right Panel)

Shows detailed information about the selected service.

### Filters Panel (Left Panel)

Provides filtering options to narrow down the service list.

---

## Working with Services

### Refreshing the Service List

* Click **Tools → Refresh Services** or press **F5**
* The status bar will display "Refreshing services..." during the operation

### Saving Services

1. Select one or more services in the services table
   * Use Ctrl+Click for multiple selection
   * Use Shift+Click for range selection
2. Click **File → Save Selected Services** or press **Ctrl+S**
3. Choose a location and filename for the JSON file
4. Click **Save**

> **Tip**: Right-click on selected services and choose "Save Selected Services" from the context menu.

### Loading and Creating Services

1. Click **File → Load Services** or press **Ctrl+O**
2. Select a previously saved JSON file
3. In the confirmation dialog, review the services to be created
4. Check/uncheck services as needed
5. Click **OK** to create the selected services

### Cancelling Services

1. Select one or more services in the services table
2. Click **Tools → Cancel Selected Services** or press **Ctrl+D**
3. Confirm the cancellation when prompted
4. A summary of results will be displayed after the operation

---

## Filtering Services

VIPrestore offers powerful filtering capabilities to help you manage large service lists:

### Basic Filters Tab

#### Text Filters
* **Source**: Filter services by source endpoint name
* **Destination**: Filter services by destination endpoint name

Both source and destination filters support logical operators:
* Use "**OR**" between terms to match either term (e.g., "London OR Paris")
* Use "**AND**" between terms to require both terms (e.g., "Studio AND Camera")

#### Time Filters
* **Start Time**: Filter services by start date/time
* **End Time**: Filter services by end date/time
* **Enable Time Filtering**: Checkbox to activate/deactivate time filters

#### Profile Filters
* Check/uncheck profile names to show/hide services with those profiles
* Only profiles in use by current services are displayed

### Reset Filters
Click the **Reset Filters** button to clear all filters and display all services.

---

## Service Details

When you select a service in the main table, the Service Details panel displays comprehensive information about that service:

### Key Information Fields

* **Service Kind**: Type of service (Endpoint-Based or Group-Based)
* **ServiceID**: Unique identifier
* **AllocationState**: Current allocation status
* **From/To**: Source and destination endpoints
* **Start/End**: Service timing information
* **Profile**: Service quality and routing profile
* **Group Parent**: For child services, shows the parent group ID (clickable)
* **Audit History**: Record of service changes
* **Res**: Network resource allocation (used for map visualization)

### Interacting with Details

* Click on a Group Parent field to view details about the parent group service
* Right-click on fields to copy text values
* Right-click on the "res" field to access the network map visualization

---

## Network Visualization

VIPrestore can visualize the network path of a service:

### Viewing the Network Map

1. Select a service in the main table
2. In the Service Details panel, right-click on the "res" field
3. Select "Show Map" from the context menu

### Map Features

* Visual representation of the main and spare (protection) paths
* Color coding: 
  * **Blue** for main path
  * **Orange** for spare path
* Clickable nodes with detailed information in tooltips
* Ability to pan and zoom the network view

---

## Remote Systems Configuration

VIPrestore can connect to multiple VideoIPath systems. You can manage these connections through the Systems Editor:

### Opening the Systems Editor

* Click **Tools → Edit Systems**

### Adding a New System

1. In the Systems Editor, click **Add**
2. Enter a name for the system (e.g., "Production" or "Lab")
3. Enter the URL (e.g., "https://vip.example.com/")
4. Click **Save**

### Editing Existing Systems

1. Select a system from the list
2. Modify the name or URL
3. Click **Save**

### Reordering Systems

* Drag and drop systems in the list to change their order
* The order determines how they appear in the login dropdown

### Removing Systems

1. Select a system from the list
2. Click **Remove**
3. Confirm the deletion
4. Click **Save**

---

## Application Updates

VIPrestore automatically checks for updates when launched:

### Update Process

1. If an update is available, you'll see an update dialog showing:
   * Current version
   * New version available
   * List of changes in the new version
2. Click **Download & Install** to download and install the update
3. Click **Cancel** to skip the update

### Manual Update Check

* Currently not available in the UI
* The application will check again on next startup

---

## Troubleshooting

### Connection Issues

**Cannot connect to VideoIPath system**:
* Verify the URL is correct in the systems configuration
* Check your network connection
* Ensure your username and password are correct
* Try using HTTP instead of HTTPS if SSL issues persist

### SSL Certificate Warnings

* VIPrestore validates SSL certificates for secure connections
* If you receive an SSL warning, it means the server's certificate is invalid or not trusted
* Options:
  1. Verify you're connecting to the correct server
  2. Report the issue to your system administrator
  3. Accept the risk and continue (less secure)

### Service Loading/Saving Issues

* **Cannot save services**: Ensure you have write permissions to the target directory
* **Cannot load services**: Verify the file format is valid JSON and contains service data
* **Service creation fails**: Check that your user has sufficient permissions in VideoIPath

### Application Crashes

Logs are stored in:
* Windows: `%LOCALAPPDATA%\VIPrestore\viprestore_[date]_[time].log`
* macOS: `~/Library/Application Support/VIPrestore/viprestore_[date]_[time].log`
* Linux: `~/.config/VIPrestore/viprestore_[date]_[time].log`

Please include these logs when reporting issues.

---

## Technical Reference

### Configuration Files

* **remotesystems.json**: Located in your user configuration directory, contains connection information for VideoIPath systems
* **version.txt**: Contains the current application version

### Command Line Options

VIPrestore does not currently support command line options.

### Data Storage

* Service data is saved in JSON format
* The structure includes service definitions and scheduling information
* Example format:

```json
{
  "service-id": {
    "scheduleInfo": {
      "startTimestamp": 1652918400000,
      "type": "once",
      "endTimestamp": 1652922000000
    },
    "serviceDefinition": {
      "from": "endpoint-id-1",
      "to": "endpoint-id-2",
      "fromLabel": "Source Name",
      "toLabel": "Destination Name",
      "profileId": "profile-id",
      "profileName": "Profile Name",
      "type": "connection"
    }
  }
}
```

### Network Requirements

* VIPrestore requires HTTP/HTTPS access to VideoIPath API endpoints
* Default ports: 80 (HTTP) or 443 (HTTPS)
* All API calls use standard REST methods

---

*© 2025 - VIPrestore Team*