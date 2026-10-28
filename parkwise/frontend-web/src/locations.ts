import { api } from "./api";
import type { CollegeFacility, CollegeSession, LocationReport } from "./types";

const esc = (value: unknown) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;"}[c]!));
const message = (error: unknown) => error instanceof Error ? error.message : "Unable to complete this action.";
let selected: CollegeFacility | undefined;
let places: CollegeFacility[] = [];
let report: LocationReport | undefined;
let adminMode = false;

function localTime(value: string, timezone: string) {
  return new Date(value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`).toLocaleString("en-IN", {timeZone: timezone});
}
function map(place: CollegeFacility) {
  if (place.latitude === null || place.longitude === null) return '<div class="state">Save latitude and longitude to show this location on the map.</div>';
  const lat = place.latitude, lon = place.longitude;
  const box = [lon-.004, lat-.003, lon+.004, lat+.003].join(",");
  return `<iframe title="Map of ${esc(place.name)}" src="https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(box)}&layer=mapnik&marker=${lat}%2C${lon}" loading="lazy" referrerpolicy="no-referrer" style="width:100%;height:300px;border:0;border-radius:12px"></iframe><small class="muted">${lat}, ${lon} · © OpenStreetMap contributors</small>`;
}
function configForm(place?: CollegeFacility) {
  return `<form id="${place ? "location-config" : "location-create"}"><label>Place name<input name="name" value="${esc(place?.name)}" minlength="2" maxlength="160" required /></label><label>Address<input name="address" value="${esc(place?.address)}" minlength="5" required /></label><div class="two-column"><label>Latitude<input name="latitude" type="number" min="-90" max="90" step="any" value="${place?.latitude ?? ""}" required /></label><label>Longitude<input name="longitude" type="number" min="-180" max="180" step="any" value="${place?.longitude ?? ""}" required /></label></div><label>Capacity<input name="capacity" type="number" min="1" max="5000" value="${place?.capacity ?? 20}" required /></label><label>Timezone<input name="timezone" value="${esc(place?.timezone || "Asia/Kolkata")}" required /></label><button class="primary-button" type="submit">${place ? "Save configuration" : "Add location"}</button><div data-form-message role="status"></div></form>`;
}
function slots(place: CollegeFacility) {
  return `<section class="panel"><h2>Slots · ${esc(place.name)}</h2><p>${place.available} available / ${place.capacity} total</p><div class="slot-grid">${place.slots.map(s => `<div class="slot slot-${s.status.toLowerCase()}"><b>${esc(s.code)}</b><span>${esc(s.status.replaceAll("_", " "))}</span><small class="slot-vehicle">${esc(s.vehicle_number || (s.status === "AVAILABLE" ? "No vehicle" : "Vehicle not recorded"))}</small></div>`).join("") || '<p>No slots configured.</p>'}</div></section>`;
}
function picker() {
  return `<div class="section-heading"><h2>Parking locations</h2><span class="muted">Select a place to see its details</span></div><div class="place-grid">${places.map(p => `<button type="button" class="place-card location-card ${selected?.id === p.id ? "location-selected" : ""}" data-location="${p.id}"><h3>${esc(p.name)}</h3><p>${esc(p.address)}</p><strong>${p.available} available / ${p.capacity}</strong><small>${p.occupied} occupied</small></button>`).join("") || '<p>No locations configured yet.</p>'}</div>`;
}
function metrics(place: CollegeFacility) {
  return `<div class="metrics">${[["Total spaces",place.capacity],["Occupied",place.occupied],["Available",place.available]].map(([name,value]) => `<article class="metric-card"><span>${name}</span><strong>${value}</strong></article>`).join("")}<article class="metric-card"><span>Location timezone</span><strong style="font-size:1rem">${esc(place.timezone)}</strong><small>${localTime(place.last_updated,place.timezone)}</small></article></div>`;
}
function recordTable(data: LocationReport) {
  return `<p>${esc(data.place_name)} · ${data.selected_date} · ${esc(data.timezone)} · ${data.rows.length} record(s)</p><p class="muted">Sessions present during the selected date. Status shows the slot’s current state; times use this location’s timezone.</p><div class="table-wrap"><table><thead><tr>${data.columns.map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${data.rows.map(row=>`<tr>${row.map(v=>`<td>${esc(v || "—")}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="8">No parking records for this location and date.</td></tr>`}</tbody></table></div>`;
}
export async function locationDashboard(isAdmin: boolean) {
  adminMode = isAdmin;
  report = undefined;
  places = await api.locations();
  const requested = new URLSearchParams(location.search).get("facility_id");
  selected = requested ? places.find(p=>p.id === Number(requested)) : [...places].sort((a,b)=>b.id-a.id)[0];
  if (requested && !selected) throw new Error("This parking location is no longer available. Open a current QR code.");
  let html = `<div class="page-title"><span class="eyebrow">${isAdmin ? "ADMIN DASHBOARD" : "USER PARKING"}</span><h1>${isAdmin ? "Parking locations control" : "Choose your parking location"}</h1></div>${picker()}`;
  if (isAdmin) html += `<details class="form-panel"><summary>Add new location</summary>${configForm()}</details>`;
  if (!selected) return html;
  const place = selected;
  html += `<div class="section-heading"><div><span class="eyebrow">SELECTED LOCATION</span><h2>${esc(place.name)}</h2><p>${esc(place.address)}</p></div><button class="secondary-button" id="location-refresh">Refresh availability</button></div>${metrics(place)}`;
  if (isAdmin) {
    const [zones, gates] = await Promise.all([api.zones(place.id), api.gates(place.id)]);
    const scanners = (await Promise.all(gates.map(async gate => (await api.scanners(gate.id)).map(scanner=>({...scanner,gate_name:gate.name}))))).flat();
    html += `<div class="two-column"><section class="form-panel"><h2>Location configuration</h2>${configForm(place)}</section><section class="panel"><h2>Entry / exit QR and location</h2><p>Scan with your phone camera to open this place’s entry or exit page. Sign in, then confirm the action. Connect the phone and this computer to the same Wi-Fi.</p><div class="two-column">${(["entry","exit"] as const).map(direction=>`<div><h3>${direction === "entry" ? "Entry QR" : "Exit QR"}</h3><img data-location-qr="${direction}" alt="${direction} QR for ${esc(place.name)}" width="200" height="200" hidden /><p data-location-qr-message="${direction}" role="status">Loading QR…</p><button type="button" class="secondary-button" data-location-qr-download="${direction}">Download ${direction} QR</button></div>`).join("")}</div><h3>Map of ${esc(place.name)}</h3>${map(place)}</section></div>${slots(place)}<section class="panel"><h2>Zones</h2><div class="table-wrap"><table><thead><tr><th>Name</th><th>Vehicle type</th><th>Capacity</th><th>Status</th></tr></thead><tbody>${zones.map(z=>`<tr><td>${esc(z.name)}</td><td>${esc(z.vehicle_type)}</td><td>${z.capacity}</td><td>${z.is_active ? "Active" : "Inactive"}</td></tr>`).join("")}</tbody></table></div></section><section class="panel"><h2>Gates and scanners · ${esc(place.name)}</h2><div class="table-wrap"><table><thead><tr><th>Gate</th><th>Direction</th><th>Status</th></tr></thead><tbody>${gates.map(g=>`<tr><td>${esc(g.name)}</td><td>${g.gate_type}</td><td>${g.is_active ? "Active" : "Inactive"}</td></tr>`).join("") || '<tr><td colspan="3">No gates registered for this place.</td></tr>'}</tbody></table><table><thead><tr><th>Scanner</th><th>Gate</th><th>Device identifier</th><th>Last seen</th><th>Status</th></tr></thead><tbody>${scanners.map(s=>`<tr><td>${esc(s.name)}</td><td>${esc(s.gate_name)}</td><td>${esc(s.device_identifier)}</td><td>${s.last_seen_at ? localTime(s.last_seen_at,place.timezone) : "Never"}</td><td>${s.is_active ? "Active" : "Inactive"}</td></tr>`).join("") || '<tr><td colspan="5">No scanners registered for this place.</td></tr>'}</tbody></table></div><div class="two-column"><form id="location-gate-create"><h3>Add gate</h3><label>Gate name<input name="name" minlength="2" required /></label><label>Direction<select name="gate_type"><option>ENTRY</option><option>EXIT</option><option>BOTH</option></select></label><button class="secondary-button">Add gate</button><div data-form-message></div></form><form id="location-scanner-create"><h3>Add scanner</h3><label>Gate<select name="gate_id" required>${gates.map(g=>`<option value="${g.id}">${esc(g.name)}</option>`).join("")}</select></label><label>Scanner name<input name="name" minlength="2" required /></label><label>Device identifier<input name="device_identifier" minlength="3" required /></label><button class="secondary-button" ${gates.length ? "" : "disabled"}>Register scanner</button><div data-form-message></div></form></div></section><section class="panel"><h2>Parking records and downloads</h2><form id="location-report-form"><div class="two-column"><label>Location<select name="facility_id" required>${places.map(p=>`<option value="${p.id}" ${p.id===place.id ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></label><label>Date<input type="date" name="selected_date" required /></label></div><button class="primary-button">Show records</button><p data-form-message role="status">Select a location and date before downloading.</p></form><div id="location-report-preview"></div><button class="secondary-button" data-location-export="csv" disabled>Download CSV</button> <button class="secondary-button" data-location-export="xlsx" disabled>Download Excel</button></section>`;
  } else {
    const [profile, history] = await Promise.all([api.collegeProfile(), api.collegeHistory(place.id)]);
    const active = history.find(s=>s.status === "ACTIVE");
    const flow = new URLSearchParams(location.search).get("flow");
    html += `<section class="panel"><h2>${flow === "entry" ? "Confirm parking entry" : flow === "exit" ? "Confirm parking exit" : "Your parking"} · ${esc(place.name)}</h2>${flow ? '<p>QR scanned successfully. Check the location and confirm below.</p>' : ""}${active ? `<p>Vehicle ${esc(active.vehicle_number)} · slot ${esc(active.space)} · entered ${localTime(active.entry_time,place.timezone)}</p><button class="primary-button" id="location-exit">Confirm exit / free my slot</button>` : `<p>Save your vehicle profile, then confirm entry to receive an available slot.</p>${flow === "exit" ? '<p>No active parking session at this location.</p>' : '<button class="primary-button" id="location-entry">Confirm entry / park my vehicle</button>'}`}<div id="location-action-message" role="status"></div></section><div class="two-column"><section class="panel"><h2>Location map</h2>${map(place)}</section>${slots(place)}</div><section class="form-panel"><h2>Your profile</h2><form id="location-profile"><label>Full name<input name="full_name" value="${esc(profile.full_name)}" required /></label><label>Phone<input name="phone" value="${esc(profile.phone)}" /></label><label>Vehicle registration<input name="registration_number" value="${esc(profile.registration_number)}" required /></label><button class="primary-button">Save profile</button><div data-form-message role="status"></div></form></section><section class="panel"><h2>Your history · ${esc(place.name)}</h2><div class="table-wrap"><table><thead><tr><th>Place</th><th>Vehicle</th><th>Slot</th><th>Entry</th><th>Exit</th><th>Status</th></tr></thead><tbody>${history.map(s=>`<tr><td>${esc(s.place_name)}</td><td>${esc(s.vehicle_number)}</td><td>${esc(s.space)}</td><td>${localTime(s.entry_time,place.timezone)}</td><td>${s.exit_time ? localTime(s.exit_time,place.timezone) : "—"}</td><td>${esc(s.status)}</td></tr>`).join("") || '<tr><td colspan="6">No records for this location.</td></tr>'}</tbody></table></div></section>`;
  }
  return html;
}
function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob), link = document.createElement("a");
  link.href = url; link.download = filename;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function selectLocation(id: number, refresh: () => Promise<void>) {
  const url = new URL(location.href);
  url.search = new URLSearchParams({facility_id:String(id)}).toString();
  history.replaceState({},"",url);
  void refresh();
}
export function bindLocationDashboard(refresh: () => Promise<void>) {
  const place = selected;
  document.querySelectorAll<HTMLButtonElement>("[data-location]").forEach(button=>button.addEventListener("click",()=>selectLocation(Number(button.dataset.location),refresh)));
  document.querySelector("#location-refresh")?.addEventListener("click",()=>void refresh());
  function formAction(id: string, action: (data: FormData, form: HTMLFormElement) => Promise<void>) {
    document.querySelector<HTMLFormElement>(`#${id}`)?.addEventListener("submit",async event=>{
      event.preventDefault();
      const form = event.currentTarget as HTMLFormElement, button = form.querySelector<HTMLButtonElement>("button")!, output = form.querySelector<HTMLElement>("[data-form-message]")!;
      button.disabled = true; output.textContent = "Saving…";
      try { await action(new FormData(form),form); } catch(error) { output.textContent = message(error); }
      finally { button.disabled = false; }
    });
  }
  function config(data: FormData) {
    return {name:String(data.get("name")),address:String(data.get("address")),latitude:Number(data.get("latitude")),longitude:Number(data.get("longitude")),capacity:Number(data.get("capacity")),timezone:String(data.get("timezone")),permitted_email_domains:[]};
  }
  formAction("location-create",async data=>{ const created = await api.addLocation(config(data)); selectLocation(created.id,refresh); });
  if (!place) return;
  formAction("location-config",async data=>{ await api.collegeConfig(config(data),place.id); await refresh(); });
  formAction("location-gate-create",async data=>{ await api.createGate(place.id,{name:String(data.get("name")),gate_type:String(data.get("gate_type")),is_active:true}); await refresh(); });
  formAction("location-scanner-create",async (data,form)=>{
    const scanner = await api.createScanner(Number(data.get("gate_id")),{name:String(data.get("name")),device_identifier:String(data.get("device_identifier")),is_active:true});
    const output = form.querySelector<HTMLElement>("[data-form-message]")!;
    output.textContent = `Scanner registered. Save this one-time device key securely: ${scanner.api_key}`;
    output.style.overflowWrap = "anywhere";
  });
  formAction("location-profile",async (data,form)=>{ await api.updateCollegeProfile({full_name:String(data.get("full_name")),phone:String(data.get("phone")) || null,registration_number:String(data.get("registration_number"))}); form.querySelector<HTMLElement>("[data-form-message]")!.textContent="Profile saved."; });
  for (const direction of ["entry","exit"] as const) {
    document.querySelector<HTMLButtonElement>(`#location-${direction}`)?.addEventListener("click",async event=>{
      const button = event.currentTarget as HTMLButtonElement, output = document.querySelector<HTMLElement>("#location-action-message")!;
      button.disabled = true; output.textContent="Confirming…";
      try { if(direction === "entry") await api.collegeEntry(place.id); else await api.collegeExit(place.id); await refresh(); }
      catch(error) { output.textContent=message(error); } finally { button.disabled=false; }
    });
    if (!adminMode) continue;
    const image = document.querySelector<HTMLImageElement>(`[data-location-qr="${direction}"]`), output = document.querySelector<HTMLElement>(`[data-location-qr-message="${direction}"]`);
    if(image && output) void api.collegeQrImage(direction,place.id).then(blob=>{
      if (!image.isConnected) return;
      const url=URL.createObjectURL(blob); image.onload=()=>URL.revokeObjectURL(url); image.onerror=()=>{URL.revokeObjectURL(url);output.textContent="Unable to display QR.";}; image.src=url;image.hidden=false;output.textContent="";
    }).catch(error=>{output.textContent=message(error);});
    document.querySelector<HTMLButtonElement>(`[data-location-qr-download="${direction}"]`)?.addEventListener("click",async event=>{
      const button=event.currentTarget as HTMLButtonElement;button.disabled=true;
      try {download(await api.collegeQrImage(direction,place.id),`location-${place.id}-${direction}.png`);} catch(error){if(output)output.textContent=message(error);} finally{button.disabled=false;}
    });
  }
  const reportForm = document.querySelector<HTMLFormElement>("#location-report-form");
  reportForm?.addEventListener("input",()=>{report=undefined;document.querySelectorAll<HTMLButtonElement>("[data-location-export]").forEach(b=>b.disabled=true);document.querySelector("#location-report-preview")!.innerHTML="";});
  formAction("location-report-form",async(data,form)=>{
    const result = await api.locationReport(Number(data.get("facility_id")),String(data.get("selected_date")));
    // Do not enable a download if the filter changed while the response was in flight.
    const latest = new FormData(form);
    if(String(latest.get("facility_id"))!==String(result.facility_id) || latest.get("selected_date")!==result.selected_date) return;
    report=result;document.querySelector("#location-report-preview")!.innerHTML=recordTable(result);
    form.querySelector<HTMLElement>("[data-form-message]")!.textContent="Records ready. Choose CSV or Excel.";
    document.querySelectorAll<HTMLButtonElement>("[data-location-export]").forEach(b=>b.disabled=false);
  });
  document.querySelectorAll<HTMLButtonElement>("[data-location-export]").forEach(button=>button.addEventListener("click",async()=>{
    if(!report) return;
    const current=report, format=button.dataset.locationExport;button.disabled=true;
    try{
      const blob=format==="csv" ? new Blob([await api.exportCsv(1,current.facility_id,current.selected_date)],{type:"text/csv;charset=utf-8"}) : await api.exportXlsx(1,current.facility_id,current.selected_date);
      download(blob,`parkwise-location-${current.facility_id}-${current.selected_date}.${format}`);
    }catch(error){reportForm!.querySelector<HTMLElement>("[data-form-message]")!.textContent=message(error);}finally{button.disabled=!report;}
  }));
}
