import { useMemo } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, Polyline, TileLayer, Tooltip } from "react-leaflet";
import type { Places, Plan } from "../api/types";
import { DAY_COLOURS, DAY_TEXT } from "./DayColours";
import { Skeleton } from "./ui";

type LatLon = [number, number];

const esc = (t: string) => t.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

function pin(label: string, colour: string, text: string, name: string, big = false) {
  const size = big ? 30 : 24;
  return L.divIcon({
    className: "",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `<span role="img" aria-label="${esc(name)}" style="display:flex;align-items:center;justify-content:center;width:${size}px;height:${size}px;border-radius:9999px;`
      + `background:${colour};color:${text};font:600 ${big ? 13 : 12}px system-ui;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4)">${esc(label)}</span>`,
  });
}

/** Hotel and each day's stops, with each day's route as straight lines in its own colour (UI-FR-05, FR-051). */
export default function DayMap({ plan, places }: { plan: Plan; places?: Places }) {
  const where = useMemo(() => {
    const m = new Map<string, LatLon>();
    places?.attractions.forEach((a) => m.set(a.id, [a.lat, a.lon]));
    places?.hotels.forEach((h) => m.set(h.id, [h.lat, h.lon]));
    return m;
  }, [places]);
  if (!places) return <Skeleton lines={4} />;
  const hotel = where.get(plan.hotel.hotel_id);
  if (!hotel) return <p className="muted">Map unavailable for this plan.</p>;
  const days = plan.days.filter((d) => d.stops.length).map((d) => ({
    day: d.day,
    colour: DAY_COLOURS[(d.day - 1) % DAY_COLOURS.length],
    text: DAY_TEXT[(d.day - 1) % DAY_TEXT.length],
    stops: d.stops.map((s) => ({ id: s.attraction_id, name: s.name, at: where.get(s.attraction_id) })).filter((s) => s.at) as
      { id: string; name: string; at: LatLon }[],
  }));
  const points: LatLon[] = [hotel, ...days.flatMap((d) => d.stops.map((s) => s.at))];
  const bounds = L.latLngBounds(points).pad(0.15);
  return (
    <figure className="space-y-2">
      <div className="h-80 overflow-hidden rounded-lg border border-sand-200 sm:h-96">
        <MapContainer bounds={bounds} scrollWheelZoom={false} className="h-full w-full" aria-label="Map of the plan">
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                     attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
          {days.map((d) => (
            <Polyline key={`r${d.day}`} positions={[hotel, ...d.stops.map((s) => s.at), hotel]}
                      pathOptions={{ color: d.colour, weight: 4, opacity: 1 }} />
          ))}
          {days.flatMap((d) => d.stops.map((s, i) => (
            <Marker key={`${d.day}-${s.id}`} position={s.at} icon={pin(String(i + 1), d.colour, d.text, `Day ${d.day}, stop ${i + 1}: ${s.name}`)}
                    title={`Day ${d.day}, stop ${i + 1}: ${s.name}`}>
              <Tooltip>Day {d.day} · {i + 1}. {s.name}</Tooltip>
            </Marker>
          )))}
          <Marker position={hotel} icon={pin("H", "#1c2430", "#ffffff", `Hotel: ${plan.hotel.name}`, true)}
                  title={`Hotel: ${plan.hotel.name}`}>
            <Tooltip>{plan.hotel.name}</Tooltip>
          </Marker>
        </MapContainer>
      </div>
      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-700">
        <span className="font-medium">Routes shown as straight lines.</span>
        <span className="inline-flex items-center gap-1"><span aria-hidden className="inline-block h-3 w-3 rounded-full bg-ink-900" /> Hotel</span>
        {days.map((d) => (
          <span key={d.day} className="inline-flex items-center gap-1">
            <span aria-hidden className="inline-block h-1 w-5 rounded" style={{ background: d.colour }} /> Day {d.day}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
