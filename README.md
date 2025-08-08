# Viam Haversine Component

A Viam component that calculates the distance between two geographical points using the haversine formula. 

This component can either:
1. Calculate distances between data from two configured sensors (via get_readings)
2. Calculate distances between two manually provided coordinates (via do_command)

The distances are provided in three units:
- Kilometers
- Miles
- Nautical Miles

## Model mcvella:haversine:haversine

This model implements a sensor component that calculates the great-circle distance between two points on a sphere using the haversine formula.

### Configuration

The following configuration template shows how to set up the haversine component:

```json
{
  "sensor_1": {
    "name": "<sensor_name>",
    "latitude": "<path.to.latitude>",
    "longitude": "<path.to.longitude>"
  },
  "sensor_2": {
    "name": "<sensor_name>",
    "latitude": "<path.to.latitude>",
    "longitude": "<path.to.longitude>"
  }
}
```

#### Attributes

The following attributes are optional for this model:

| Name | Type | Inclusion | Description |
|------|------|-----------|-------------|
| `sensor_1` | object | Optional | Configuration for the first location sensor |
| `sensor_2` | object | Optional | Configuration for the second location sensor |

If you don't configure both sensors, only the `do_command()` method will be fully functional. `get_readings()` will return an empty object if both sensors are not configured.

Each sensor configuration requires:
- `name`: The name of the sensor component
- `latitude`: JSON path to the latitude value in the sensor's readings
- `longitude`: JSON path to the longitude value in the sensor's readings

#### Example Configuration

```json
{
  "sensor_1": {
    "name": "gps1",
    "latitude": "position.lat",
    "longitude": "position.lng"
  },
  "sensor_2": {
    "name": "phone_data",
    "latitude": "loc.latitude",
    "longitude": "loc.longitude"
  }
}
```

### Methods

#### get_readings()

Returns the distance between the two configured sensor readings. The method will:
1. Return an empty object ({}) if both sensors are not configured
2. Get readings from both configured sensors
3. Extract latitude and longitude using the configured paths
4. Calculate distances in multiple units

Example response when sensors are configured:
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

