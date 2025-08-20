# Viam Haversine Component

A Viam component that calculates the distance between two geographical points using the haversine formula. 

This component can either:
1. Calculate distances between data from two configured sensors (via get_readings)
2. Calculate distances between two manually provided coordinates (via do_command)

The distances are provided in three units:
- Kilometers
- Miles
- Nautical Miles

## Model viam-soleng:haversine:haversine

This model implements a sensor component that calculates the great-circle distance between two points on a sphere using the haversine formula.

### Supported Sensor Types

This component supports both **Sensor** and **MovementSensor** components as data sources. The component will automatically detect the type of each configured sensor and cast it appropriately. Both sensor types provide a `get_readings()` method that returns the same data format, so they work seamlessly with this component.

### Configuration

The following configuration template shows how to set up the haversine component:

```json
{
  "sensor_1": {
    "name": "<sensor_name>",
    "latitude": "<path.to.latitude>",
    "longitude": "<path.to.longitude>",
    "updated": "<path.to.timestamp>",
    "expire": "<duration>"
  },
  "sensor_2": {
    "name": "<sensor_name>",
    "latitude": "<path.to.latitude>",
    "longitude": "<path.to.longitude>",
    "updated": "<path.to.timestamp>",
    "expire": "<duration>"
  }
}
```

#### Attributes

The following attributes are optional for this model:

| Name | Type | Inclusion | Description |
|------|------|-----------|-------------|
| `sensor_1` | object | Optional | Configuration for the first location sensor (Sensor or MovementSensor) |
| `sensor_2` | object | Optional | Configuration for the second location sensor (Sensor or MovementSensor) |

If you don't configure both sensors, only the `do_command()` method will be fully functional. `get_readings()` will return an empty object if both sensors are not configured.

Each sensor configuration requires:
- `name`: The name of the sensor component (can be either Sensor or MovementSensor)
- `latitude`: JSON path to the latitude value in the sensor's readings
- `longitude`: JSON path to the longitude value in the sensor's readings

Each sensor configuration optionally supports:
- `updated`: JSON path to an ISO8601 timestamp field (e.g., "2023-12-01T10:30:00Z")
- `expire`: Duration string after which the reading is considered stale (e.g., "1d", "12h", "10m", "30s", "100ms")

If both `updated` and `expire` are specified for a sensor, the reading will be considered invalid and no distance will be calculated if the timestamp is older than the expire duration.

#### Example Configuration

```json
{
  "sensor_1": {
    "name": "gps1",
    "latitude": "position.lat",
    "longitude": "position.lng",
    "updated": "timestamp",
    "expire": "5m"
  },
  "sensor_2": {
    "name": "phone_data",
    "latitude": "loc.latitude",
    "longitude": "loc.longitude",
    "updated": "last_updated",
    "expire": "1h"
  }
}
```

In this example:
- `gps1` could be a MovementSensor (like a GPS module)
- `phone_data` could be a regular Sensor (like a data source from a phone app)

The component will automatically detect and handle both types correctly.

### Methods

#### get_readings()

Returns the distance between the two configured sensors. The method will:
1. Return an empty object ({}) if both sensors are not configured
2. Check if sensor readings are still valid (if updated/expire fields are configured)
3. Return an empty object ({}) if any sensor reading has expired
4. Get readings from both configured sensors (works with both Sensor and MovementSensor)
5. Extract latitude and longitude using the configured paths
6. Calculate distances in multiple units

Example response when sensors are configured and readings are valid:
```json
{
  "distance_km": 392.21,
  "distance_miles": 243.71,
  "distance_nautical_miles": 211.78,
  "location_1": {
    "latitude": 45.7597,
    "longitude": 4.8422
  },
  "location_2": {
    "latitude": 48.8567,
    "longitude": 2.3508
  }
}
```

#### do_command()

Calculates the distance between two manually provided coordinates. This method works regardless of sensor configuration, making it useful for one-off distance calculations or when you don't have physical sensors.

Example command:
```json
{
  "location_1": {
    "latitude": 45.7597,
    "longitude": 4.8422
  },
  "location_2": {
    "latitude": 48.8567,
    "longitude": 2.3508
  }
}
```

The response format is identical to get_readings().

### Dependencies

This component requires:
- Python 3.5 or later
- haversine package (version 2.9.0)
- viam-sdk

### Error Handling

The component will:
- Return an empty object from get_readings() if both sensors are not configured
- Return an empty object from get_readings() if any sensor reading has expired
- Log a warning during startup if sensors are configured but not found
- Log a warning if sensor readings have expired
- Log info messages showing which type of sensor (Sensor or MovementSensor) was detected
- Raise errors if:
  - Sensor configuration is provided but missing required fields
  - Invalid coordinates are provided to do_command()
  - Sensor readings don't contain the expected data at the configured paths
  - Invalid duration format is provided in expire field
  - A component is neither Sensor nor MovementSensor

