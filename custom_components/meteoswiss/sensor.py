import logging
import pprint
import typing
from datetime import date, datetime
from decimal import Decimal

from hamsclientfork.client import StationType
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.meteoswiss import MeteoSwissDataUpdateCoordinator
from custom_components.meteoswiss.const import (
    CONF_POSTCODE,
    CONF_PRECIPITATION_STATION,
    CONF_REAL_TIME_NAME,
    CONF_REAL_TIME_PRECIPITATION_NAME,
    CONF_STATION,
    DOMAIN,
    SENSOR_DATA_ID,
    SENSOR_TYPE_CLASS,
    SENSOR_TYPE_ICON,
    SENSOR_TYPE_NAME,
    SENSOR_TYPE_UNIT,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all sensors."""
    _LOGGER.debug("Starting async setup platform for sensor")
    c: MeteoSwissDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if c.weather_station:
        async_add_entities(
            [
                MeteoSwissSensor(entry.entry_id, typ, c, StationType.WEATHER)
                for typ in SENSOR_TYPES
            ],
            True,
        )
    else:
        _LOGGER.debug(
            "The data update coordinator has no real-time weather station configured"
            + " — not providing weather sensor data."
        )
    if c.precipitation_station:
        async_add_entities(
            [
                MeteoSwissSensor(entry.entry_id, typ, c, StationType.PRECIPITATION)
                for typ in SENSOR_TYPES
            ],
            True,
        )
    else:
        _LOGGER.debug(
            "The data update coordinator has no real-time precipitation station configured"
            + " — not providing precipitation sensor data."
        )


class MeteoSwissSensor(
    CoordinatorEntity[MeteoSwissDataUpdateCoordinator],
    SensorEntity,
):
    """Represents a sensor from MeteoSwiss."""

    def __init__(
        self,
        integration_id: str,
        sensor_type: typing.Any,
        coordinator: MeteoSwissDataUpdateCoordinator,
        station_type: StationType,
    ):
        super().__init__(coordinator)
        self._station_type = station_type
        self._attr_unique_id = "sensor.%s-%s%s" % (
            integration_id,
            sensor_type,
            "-precipitation" if station_type == StationType.PRECIPITATION else "",
        )
        self._state = None
        self._type = sensor_type
        self._attr_native_unit_of_measurement = SENSOR_TYPES[self._type][
            SENSOR_TYPE_UNIT
        ]
        self._attr_icon = SENSOR_TYPES[self._type][SENSOR_TYPE_ICON]
        self._attr_device_class = SENSOR_TYPES[self._type][SENSOR_TYPE_CLASS]
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._data = coordinator.data
        self._attr_station = coordinator.data[
            CONF_STATION
            if station_type == StationType.WEATHER
            else CONF_PRECIPITATION_STATION
        ]
        self._attr_postcode = coordinator.data[CONF_POSTCODE]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        x = SENSOR_TYPES[self._type][SENSOR_TYPE_NAME]
        name_key = (
            CONF_REAL_TIME_NAME
            if self._station_type == StationType.WEATHER
            else CONF_REAL_TIME_PRECIPITATION_NAME
        )
        return f"{self._data[name_key]} {x}"

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        data_ids = SENSOR_TYPES[self._type][SENSOR_DATA_ID]
        if isinstance(data_ids, str):
            data_ids = (data_ids,)
        st_data = self._data["condition_by_station"].get(self._attr_station) or {}
        for data_id in data_ids:
            try:
                val = st_data.get(data_id)
                if val is not None and val != "-":
                    return val
            except Exception:
                _LOGGER.warning(
                    "Real-time weather station returned bad data:\n%s",
                    pprint.pformat(self._data),
                )
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.native_value is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._data = self.coordinator.data
        self.async_write_ha_state()
