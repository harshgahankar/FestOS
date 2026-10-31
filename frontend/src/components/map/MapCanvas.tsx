import { useEffect } from "react";
import {
  CircleMarker,
  MapContainer,
  Marker,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import L from "leaflet";
import type { MapLocation } from "../../mapTypes";
import { typeLabel } from "../../mapTypes";
import "leaflet/dist/leaflet.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.Default.css";

export type LatLng = { latitude: number; longitude: number };

const TONE_COLOR: Record<string, string> = {
  teal: "#2fa79f",
  gold: "#d98b17",
  maroon: "#a3242b",
  grey: "#6b625a",
};

const TYPE_SYMBOL: Record<string, string> = {
  hostel_block: "H",
  external_stay: "E",
  venue: "V",
  vendor: "F",
  inventory_location: "S",
  incident_location: "!",
};

function pinIcon(location: MapLocation, showIncidents: boolean) {
  const color = TONE_COLOR[location.operational_status.color] ?? TONE_COLOR.grey;
  const symbol = TYPE_SYMBOL[location.location_type] ?? "•";
  const dashed = location.coordinates_verified ? "" : "border-style:dashed;";
  const incident = location.has_incident && showIncidents
    ? '<span class="gc-pin-alert" aria-hidden="true"></span>'
    : "";
  return L.divIcon({
    className: "gc-marker",
    html:
      `<span class="gc-pin" style="--gc-pin:${color};${dashed}">` +
      `<span class="gc-pin-symbol">${symbol}</span>${incident}</span>`,
    iconSize: [30, 38],
    iconAnchor: [15, 34],
    tooltipAnchor: [0, -30],
  });
}

function clusterIcon(cluster: { getChildCount(): number }) {
  const count = cluster.getChildCount();
  return L.divIcon({
    html: `<span class="gc-cluster">${count}</span>`,
    className: "gc-cluster-wrap",
    iconSize: L.point(40, 40),
  });
}

function ClickCatcher({ onPick }: { onPick: (point: LatLng) => void }) {
  useMapEvents({
    click(event) {
      onPick({ latitude: event.latlng.lat, longitude: event.latlng.lng });
    },
  });
  return null;
}

function ViewSync({
  center,
  zoom,
  fitRequest,
  locations,
}: {
  center: LatLng;
  zoom: number;
  fitRequest: number;
  locations: MapLocation[];
}) {
  const map = useMap();

  useEffect(() => {
    map.setView([center.latitude, center.longitude], zoom);
  }, [map, center.latitude, center.longitude, zoom]);

  useEffect(() => {
    if (!fitRequest) return;
    const points = locations
      .filter((row) => row.mapped)
      .map((row) => L.latLng(row.latitude as number, row.longitude as number));
    if (points.length) {
      map.fitBounds(L.latLngBounds(points), { padding: [48, 48], maxZoom: 18 });
    }
  }, [map, fitRequest, locations]);

  return null;
}

export default function MapCanvas({
  locations,
  center,
  zoom,
  selectedId,
  picking,
  draft,
  fitRequest,
  showIncidents = true,
  onSelect,
  onPick,
}: {
  locations: MapLocation[];
  center: LatLng;
  zoom: number;
  selectedId: number | null;
  picking: boolean;
  draft: LatLng | null;
  fitRequest: number;
  showIncidents?: boolean;
  onSelect: (id: number) => void;
  onPick: (point: LatLng) => void;
}) {
  const mapped = locations.filter(
    (row) => row.mapped && row.latitude !== null && row.longitude !== null,
  );

  return (
    <MapContainer
      center={[center.latitude, center.longitude]}
      zoom={zoom}
      minZoom={2}
      maxZoom={19}
      className={picking ? "gc-picking h-full w-full" : "h-full w-full"}
      worldCopyJump
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={19}
      />
      <ClickCatcher onPick={onPick} />
      <ViewSync
        center={center}
        zoom={zoom}
        fitRequest={fitRequest}
        locations={locations}
      />
      <MarkerClusterGroup
        chunkedLoading
        maxClusterRadius={46}
        showCoverageOnHover={false}
        spiderfyOnMaxZoom
        disableClusteringAtZoom={18}
        iconCreateFunction={clusterIcon}
      >
        {mapped.map((location) => (
          <Marker
            key={location.id}
            position={[location.latitude as number, location.longitude as number]}
            icon={pinIcon(location, showIncidents)}
            eventHandlers={{ click: () => onSelect(location.id) }}
            zIndexOffset={location.id === selectedId ? 1000 : 0}
            opacity={selectedId && selectedId !== location.id ? 0.92 : 1}
          >
            <Tooltip direction="top" offset={[0, -6]} opacity={1}>
              <div className="gc-tip">
                <strong>{location.name}</strong>
                <span>
                  {typeLabel(location.location_type)} ·{" "}
                  {location.operational_status.label}
                </span>
                {!location.coordinates_verified && <em>pin not verified</em>}
                {location.has_incident && showIncidents && (
                  <em className="gc-tip-alert">incident on site</em>
                )}
              </div>
            </Tooltip>
          </Marker>
        ))}
      </MarkerClusterGroup>
      {draft && (
        <>
          <CircleMarker
            center={[draft.latitude, draft.longitude]}
            radius={16}
            pathOptions={{
              color: "#a3242b",
              weight: 2,
              fillColor: "#f0a82f",
              fillOpacity: 0.18,
            }}
          />
          <CircleMarker
            center={[draft.latitude, draft.longitude]}
            radius={7}
            pathOptions={{
              color: "#5c0f13",
              weight: 3,
              fillColor: "#f0a82f",
              fillOpacity: 1,
            }}
          />
        </>
      )}
    </MapContainer>
  );
}
