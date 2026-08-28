"""Render one provenance-separated cloning inventory as standalone HTML."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class CloningReportError(ValueError):
    """Raised when inventory data cannot describe one plasmid report."""


def render_cloning_report(
    source_path: Path,
    inventory: Mapping[str, Any],
    external_sources: Mapping[str, Any],
    *,
    plannotate_manifest: Mapping[str, Any] | None = None,
    plannotate_output_dir: Path | None = None,
) -> str:
    """Return a self-contained report for a single-record plasmid file."""
    file_entry, record = _single_record(inventory)
    features = _mapping_list(record.get("features"))
    primers = _mapping_list(record.get("primers"))
    feature_colors = [_series_color(index) for index in range(len(features))]
    primer_colors = [
        _series_color(index + len(features)) for index in range(len(primers))
    ]
    sites = _string_int_mapping(record.get("neb_restriction_sites"))
    zero_cutters = sorted(name for name, count in sites.items() if count == 0)
    single_cutters = sorted(name for name, count in sites.items() if count == 1)
    multi_cutters = sorted(name for name, count in sites.items() if count > 1)
    selected_parts = [_selected_part(feature) for feature in features]
    selected_count = sum(part is not None for part in selected_parts)
    plannotate_rows = _plannotate_rows(
        source_path,
        plannotate_manifest,
        plannotate_output_dir,
    )

    feature_rows = "".join(
        _feature_row(index, feature, feature_colors[index])
        for index, feature in enumerate(features)
    )
    primer_rows = "".join(
        _primer_row(index, primer, primer_colors[index])
        for index, primer in enumerate(primers)
    )
    igem_rows = "".join(
        _igem_row(index, feature, selected_parts[index], feature_colors[index])
        for index, feature in enumerate(features)
    )
    plannotate_rows_html = "".join(
        _plannotate_row(index, row) for index, row in enumerate(plannotate_rows)
    )
    feature_data = [
        {
            "label": str(feature.get("label") or "unnamed feature"),
            "type": str(feature.get("feature_type") or ""),
            "start": int(feature.get("start_0_based") or 0),
            "end": int(feature.get("end_0_based_exclusive") or 0),
            "strand": feature.get("strand"),
            "color": feature_colors[index],
        }
        for index, feature in enumerate(features)
    ]
    primer_data = [
        {
            "label": str(primer.get("label") or "unnamed primer"),
            "start": int(primer.get("start_0_based") or 0),
            "end": int(primer.get("end_0_based_exclusive") or 0),
            "strand": primer.get("strand"),
            "color": primer_colors[index],
        }
        for index, primer in enumerate(primers)
    ]
    source_provenance = _source_provenance(external_sources)
    plannotate_status = _plannotate_status(plannotate_manifest)
    file_name = source_path.name
    file_sha256 = str(file_entry.get("file_sha256") or "")
    sequence_length = int(record.get("sequence_length") or 0)
    topology = str(record.get("topology") or "unknown")

    body = f"""<main id="cloning-report">
<h1>Plasmid evidence report</h1>
<p class="sub">{_esc(file_name)} · SHA-256 <code>{_esc(file_sha256)}</code></p>
<section class="metrics" aria-label="Plasmid summary">
  <div><strong>{sequence_length:,} bp</strong><span>{_esc(topology)} DNA</span></div>
  <div><strong>{len(features)}</strong><span>source features</span></div>
  <div><strong>{len(primers)}</strong><span>source primers</span></div>
  <div><strong>{selected_count}/{len(features)}</strong><span>specific iGEM parts selected</span></div>
</section>
<section class="flow" aria-label="Evidence provenance flow">
  <article class="source"><h2>Downloaded file · source truth</h2><p>Sequence, topology, feature types, coordinates, labels, qualifiers, translations, and annotated primers.</p></article>
  <span class="arrow" aria-hidden="true">→</span>
  <article class="calculated"><h2>Deterministic computation</h2><p>Biopython parsing, rule-derived functional summaries with rule evidence, primer sequences, restriction sites, and hashes.</p></article>
  <span class="arrow" aria-hidden="true">→</span>
  <article class="external"><h2>External evidence · separate</h2><p>Specific iGEM records and roles, pLannotate sequence-search candidates, and the current REBASE supplier-N catalog.</p></article>
</section>
<p class="sub">Every feature and primer instance has a stable color shared by the map and its table row. Coordinates are 0-based and end-exclusive.</p>
<div class="map"><svg id="sequence-map" viewBox="0 0 1000 190" role="img" aria-label="Color-coded linear map of {_esc(file_name)}"></svg></div>
<nav class="tabs" aria-label="Report sections">
  <button type="button" data-panel="features" aria-pressed="true">Source features</button>
  <button type="button" data-panel="primers" aria-pressed="false">Source primers</button>
  <button type="button" data-panel="igem" aria-pressed="false">Specific iGEM parts</button>
  <button type="button" data-panel="plannotate" aria-pressed="false">pLannotate</button>
  <button type="button" data-panel="enzymes" aria-pressed="false">Restriction enzymes</button>
  <button type="button" data-panel="provenance" aria-pressed="false">Provenance</button>
</nav>
<section data-panel-content="features">
  <p class="notice">Feature type, location, label, and qualifiers are copied from the source file. “Rule-derived functional summary” is generated from explicit local rules; each row exposes the rule evidence.</p>
  <div class="table-wrap"><table><thead><tr><th>#</th><th>Label</th><th>GenBank type</th><th>Location</th><th>Source description</th><th>Rule-derived functional summary</th><th>Rule evidence</th><th>All source qualifiers</th></tr></thead><tbody>{feature_rows or _empty_row(8, "No source features")}</tbody></table></div>
</section>
<section data-panel-content="primers" hidden>
  <p class="notice">Primer labels, locations, and notes are source annotations. Binding sequences are extracted from the source sequence in 5′→3′ orientation.</p>
  <div class="table-wrap"><table><thead><tr><th>#</th><th>Primer</th><th>Location</th><th>Binding sequence 5′→3′</th><th>Source qualifiers</th></tr></thead><tbody>{primer_rows or _empty_row(5, "No annotated primers")}</tbody></table></div>
</section>
<section data-panel-content="igem" hidden>
  <p class="notice">GenBank type, local functional summary, and iGEM role are different fields. A specific part is selected only when its iGEM role is functionally consistent and either its DNA or translated peptide is exact.</p>
  <div class="table-wrap"><table class="wide"><thead><tr><th>#</th><th>Source label</th><th>GenBank type</th><th>Rule-derived function</th><th>Specific iGEM part</th><th>iGEM role</th><th>iGEM description</th><th>Match evidence</th></tr></thead><tbody>{igem_rows or _empty_row(8, "No source features")}</tbody></table></div>
</section>
<section data-panel-content="plannotate" hidden>
  <p class="notice">pLannotate outputs are sequence-search candidates stored separately from the source file. Identity, coverage, fragment status, database, and descriptions remain visible.</p>
  <p>{_esc(plannotate_status)}</p>
  <div class="table-wrap"><table><thead><tr><th>#</th><th>Candidate</th><th>Type</th><th>Location</th><th>Identity</th><th>Coverage</th><th>Fragment</th><th>Database</th><th>Description</th></tr></thead><tbody>{plannotate_rows_html or _empty_row(9, "No pLannotate candidates available")}</tbody></table></div>
</section>
<section data-panel-content="enzymes" hidden>
  <p class="notice">Cut counts are computed from the source sequence with Biopython's supplier-N catalog. REBASE provenance establishes catalog freshness; it does not alter the sequence.</p>
  <div class="chips"><span>{len(sites)} tested</span><span>{len(zero_cutters)} zero-cut</span><span>{len(single_cutters)} single-cut</span><span>{len(multi_cutters)} multi-cut</span></div>
  <details open><summary>Single cutters ({len(single_cutters)})</summary><p>{_chip_list(single_cutters)}</p></details>
  <details><summary>Multi-cutters ({len(multi_cutters)})</summary><p>{_chip_list(multi_cutters)}</p></details>
  <details><summary>Zero cutters ({len(zero_cutters)})</summary><p>{_chip_list(zero_cutters)}</p></details>
</section>
<section data-panel-content="provenance" hidden>
  <table><tbody>
    <tr><th>Source file</th><td>{_esc(source_path.resolve())}</td></tr>
    <tr><th>File SHA-256</th><td><code>{_esc(file_sha256)}</code></td></tr>
    <tr><th>Sequence SHA-256</th><td><code>{_esc(record.get("sequence_sha256") or "")}</code></td></tr>
    <tr><th>Parse warnings</th><td>{_esc(json.dumps(file_entry.get("parse_warnings") or []))}</td></tr>
    <tr><th>Functional inference</th><td>GenBank feature type plus curated qualifier-pattern rules; per-role evidence is retained in inventory JSON and the source-feature table.</td></tr>
    <tr><th>iGEM</th><td>{_esc(source_provenance["igem"])}</td></tr>
    <tr><th>REBASE</th><td>{_esc(source_provenance["rebase"])}</td></tr>
    <tr><th>pLannotate</th><td>{_esc(plannotate_status)}</td></tr>
  </tbody></table>
</section>
<script>
(() => {{
  const root=document.getElementById('cloning-report');
  const features={_script_json(feature_data)};
  const primers={_script_json(primer_data)};
  const length={sequence_length};
  const svg=root.querySelector('#sequence-map');
  const ns='http://www.w3.org/2000/svg';
  const add=(tag,attrs,text)=>{{const node=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([key,value])=>node.setAttribute(key,String(value)));if(text!==undefined)node.textContent=text;svg.appendChild(node);return node;}};
  const x=bp=>38+(length?bp/length:0)*924;
  add('line',{{x1:38,y1:80,x2:962,y2:80,stroke:'var(--border)','stroke-width':2}});
  const ticks=[0,0.25,0.5,0.75,1].map(value=>Math.round(length*value));
  ticks.forEach((bp,index)=>{{const px=x(bp);add('line',{{x1:px,y1:75,x2:px,y2:85,stroke:'var(--foreground)'}});add('text',{{x:px,y:100,'text-anchor':index===0?'start':index===ticks.length-1?'end':'middle'}},bp.toLocaleString());}});
  const lanes=[24,42,60,112,130,148];
  features.forEach((feature,index)=>{{const rect=add('rect',{{x:x(feature.start),y:lanes[index%3],width:Math.max(2,x(feature.end)-x(feature.start)),height:11,fill:feature.color,opacity:.86,rx:1}});const title=document.createElementNS(ns,'title');title.textContent=`${{index+1}} · ${{feature.label}} · ${{feature.type}} · ${{feature.start}}:${{feature.end}} (${{feature.strand===-1?'-':'+'}})`;rect.appendChild(title);}});
  primers.forEach((primer,index)=>{{const line=add('line',{{x1:x(primer.start),y1:lanes[3+index%3],x2:x(primer.end),y2:lanes[3+index%3],stroke:primer.color,'stroke-width':5}});const title=document.createElementNS(ns,'title');title.textContent=`${{index+1}} · ${{primer.label}} · ${{primer.start}}:${{primer.end}} (${{primer.strand===-1?'-':'+'}})`;line.appendChild(title);}});
  add('text',{{x:38,y:14}},'GBK features');add('text',{{x:38,y:174}},'GBK primer-binding sites');
  const activate=panel=>{{const selected=root.querySelector(`button[data-panel="${{panel}}"]`);if(!selected)return;root.querySelectorAll('button[data-panel]').forEach(item=>item.setAttribute('aria-pressed',String(item===selected)));root.querySelectorAll('[data-panel-content]').forEach(item=>item.hidden=item.dataset.panelContent!==panel);}};
  root.querySelectorAll('button[data-panel]').forEach(button=>button.addEventListener('click',()=>{{activate(button.dataset.panel);history.replaceState(null,'',`#${{button.dataset.panel}}`);}}));
  activate(location.hash.slice(1)||'features');
}})();
</script>
</main>"""
    return _standalone_html(body)


def write_cloning_report(
    output_path: Path,
    source_path: Path,
    inventory: Mapping[str, Any],
    external_sources: Mapping[str, Any],
    *,
    plannotate_manifest: Mapping[str, Any] | None = None,
    plannotate_output_dir: Path | None = None,
) -> None:
    """Write a standalone report, creating its parent directory."""
    report = render_cloning_report(
        source_path,
        inventory,
        external_sources,
        plannotate_manifest=plannotate_manifest,
        plannotate_output_dir=plannotate_output_dir,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(report, encoding="utf-8")
    temporary.replace(output_path)


def _single_record(
    inventory: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    files = _mapping_list(inventory.get("files"))
    if len(files) != 1:
        raise CloningReportError("Report requires exactly one parsed plasmid file")
    records = _mapping_list(files[0].get("records"))
    if len(records) != 1:
        raise CloningReportError("Report requires exactly one sequence record")
    return files[0], records[0]


def _feature_row(index: int, feature: Mapping[str, Any], color: str) -> str:
    qualifiers = feature.get("qualifiers")
    qualifiers_mapping = qualifiers if isinstance(qualifiers, Mapping) else {}
    evidence = _role_evidence_html(feature)
    return (
        "<tr>"
        f"<td>{_swatch(color)}{index + 1}</td>"
        f"<td><strong>{_esc(feature.get('label') or 'unnamed feature')}</strong></td>"
        f"<td>{_esc(feature.get('feature_type') or '')}</td>"
        f"<td><code>{_esc(feature.get('location') or '')}</code></td>"
        f"<td>{_esc(_source_description(qualifiers_mapping))}</td>"
        f"<td>{_esc(feature.get('functional_description') or '')}</td>"
        f"<td>{evidence}</td>"
        f"<td>{_json_details(qualifiers_mapping)}</td>"
        "</tr>"
    )


def _primer_row(index: int, primer: Mapping[str, Any], color: str) -> str:
    return (
        "<tr>"
        f"<td>{_swatch(color)}{index + 1}</td>"
        f"<td><strong>{_esc(primer.get('label') or 'unnamed primer')}</strong></td>"
        f"<td><code>{_esc(primer.get('location') or '')}</code></td>"
        f"<td><code>{_esc(primer.get('binding_sequence_5to3') or '')}</code></td>"
        f"<td>{_json_details(primer.get('qualifiers') or {})}</td>"
        "</tr>"
    )


def _igem_row(
    index: int,
    feature: Mapping[str, Any],
    part: Mapping[str, Any] | None,
    color: str,
) -> str:
    if part is None:
        part_cell = "<span class='muted'>No validated specific part</span>"
        role_cell = "—"
        description_cell = "—"
        evidence_cell = "not selected"
    else:
        url = str(part.get("url") or "")
        part_cell = (
            f'<a href="{_esc(url)}" target="_blank" rel="noreferrer">'
            f"{_esc(part.get('name') or '')}: {_esc(part.get('title') or '')}</a>"
        )
        role = part.get("role")
        role_mapping = role if isinstance(role, Mapping) else {}
        role_cell = (
            f"{_esc(role_mapping.get('label') or '')} "
            f"({_esc(role_mapping.get('accession') or '')})"
        )
        description_cell = _esc(
            html.unescape(str(part.get("description") or "No description supplied"))
        )
        evidence_cell = _esc(_part_evidence(part))
    return (
        "<tr>"
        f"<td>{_swatch(color)}{index + 1}</td>"
        f"<td><strong>{_esc(feature.get('label') or 'unnamed feature')}</strong></td>"
        f"<td>{_esc(feature.get('feature_type') or '')}</td>"
        f"<td>{_esc(feature.get('functional_description') or '')}</td>"
        f"<td>{part_cell}</td><td>{role_cell}</td>"
        f"<td>{description_cell}</td><td>{evidence_cell}</td>"
        "</tr>"
    )


def _plannotate_row(index: int, row: Mapping[str, Any]) -> str:
    return (
        "<tr>"
        f"<td>{index + 1}</td>"
        f"<td><strong>{_esc(row.get('Feature') or row.get('feature') or '')}</strong></td>"
        f"<td>{_esc(row.get('Type') or row.get('feature_type') or '')}</td>"
        f"<td><code>{_esc(_plannotate_location(row))}</code></td>"
        f"<td>{_percent(row.get('percent identity', row.get('percent_identity')))}</td>"
        f"<td>{_percent(row.get('percent match length', row.get('percent_match_length')))}</td>"
        f"<td>{_esc(row.get('fragment') or '')}</td>"
        f"<td>{_esc(row.get('database') or '')}</td>"
        f"<td>{_esc(row.get('Description') or row.get('description') or '')}</td>"
        "</tr>"
    )


def _selected_part(feature: Mapping[str, Any]) -> Mapping[str, Any] | None:
    external = feature.get("external_function_candidates")
    external_mapping = external if isinstance(external, Mapping) else {}
    igem = external_mapping.get("igem_registry")
    igem_mapping = igem if isinstance(igem, Mapping) else {}
    for part in _mapping_list(igem_mapping.get("specific_parts")):
        if part.get("selected"):
            return part
    return None


def _role_evidence_html(feature: Mapping[str, Any]) -> str:
    entries = _mapping_list(feature.get("functional_role_evidence"))
    if not entries:
        return "<span class='muted'>No role assigned</span>"
    items: list[str] = []
    for entry in entries:
        role = _esc(entry.get("role") or "")
        evidence_list = _mapping_list(entry.get("evidence"))
        fragments: list[str] = []
        for evidence in evidence_list:
            if evidence.get("method") == "genbank_feature_type":
                fragments.append(
                    f"GBK type <code>{_esc(evidence.get('feature_type') or '')}</code>"
                )
            else:
                fragments.append(
                    f"<code>/{_esc(evidence.get('qualifier') or '')}</code> "
                    f"matched <code>{_esc(evidence.get('matched_term') or '')}</code>"
                )
        items.append(f"<li><code>{role}</code> ← {'; '.join(fragments)}</li>")
    return f"<ul>{''.join(items)}</ul>"


def _plannotate_rows(
    source_path: Path,
    manifest: Mapping[str, Any] | None,
    output_dir: Path | None,
) -> list[Mapping[str, Any]]:
    if manifest is None:
        return []
    results = _mapping_list(manifest.get("results"))
    result = next(
        (
            item
            for item in results
            if Path(str(item.get("source_path") or "")).resolve()
            == source_path.resolve()
        ),
        results[0] if len(results) == 1 else None,
    )
    if result is None:
        return []
    if output_dir is not None:
        for output in result.get("outputs") or []:
            name = str(output)
            if Path(name).suffix.casefold() != ".csv":
                continue
            csv_path = output_dir / name
            if csv_path.is_file():
                with csv_path.open(encoding="utf-8", newline="") as handle:
                    return [dict(row) for row in csv.DictReader(handle)]
    summary = result.get("annotation_summary")
    summary_mapping = summary if isinstance(summary, Mapping) else {}
    return _mapping_list(summary_mapping.get("annotations"))


def _plannotate_status(manifest: Mapping[str, Any] | None) -> str:
    if manifest is None:
        return "not run"
    tool = manifest.get("tool")
    tool_mapping = tool if isinstance(tool, Mapping) else {}
    summary = manifest.get("summary")
    summary_mapping = summary if isinstance(summary, Mapping) else {}
    return (
        f"pLannotate {tool_mapping.get('version') or 'unknown'}; "
        f"{summary_mapping.get('annotated_or_cached_count') or 0} annotated/cached; "
        f"{summary_mapping.get('error_count') or 0} errors"
    )


def _source_provenance(external_sources: Mapping[str, Any]) -> dict[str, str]:
    sources = external_sources.get("sources")
    sources_mapping = sources if isinstance(sources, Mapping) else {}
    igem = sources_mapping.get("igem_registry")
    rebase = sources_mapping.get("rebase_neb")
    igem_mapping = igem if isinstance(igem, Mapping) else {}
    rebase_mapping = rebase if isinstance(rebase, Mapping) else {}
    igem_source = igem_mapping.get("source")
    rebase_source = rebase_mapping.get("source")
    igem_source_mapping = igem_source if isinstance(igem_source, Mapping) else {}
    rebase_source_mapping = rebase_source if isinstance(rebase_source, Mapping) else {}
    return {
        "igem": (
            f"API {igem_source_mapping.get('api_version') or 'not fetched'}; "
            f"anonymous published records; response provenance retained in external-sources.json"
        ),
        "rebase": (
            f"release {rebase_source_mapping.get('release') or 'not fetched'} "
            f"({rebase_source_mapping.get('release_date') or 'unknown date'}); "
            "response provenance retained in external-sources.json"
        ),
    }


def _part_evidence(part: Mapping[str, Any]) -> str:
    evidence = part.get("evidence")
    evidence_mapping = evidence if isinstance(evidence, Mapping) else {}
    values: list[str] = []
    if evidence_mapping.get("nucleotide_exact"):
        values.append("exact DNA")
    else:
        identity = evidence_mapping.get("same_length_nucleotide_identity_percent")
        if isinstance(identity, (int, float)):
            values.append(f"{identity:.3f}% same-length DNA identity")
    if evidence_mapping.get("translated_peptide_exact"):
        values.append("exact translated peptide")
    return " · ".join(values) or "not sequence-verified"


def _source_description(qualifiers: Mapping[str, Any]) -> str:
    for key in ("note", "product", "bound_moiety", "function"):
        values = qualifiers.get(key)
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            if values:
                return str(values[0])
    return "—"


def _series_color(index: int) -> str:
    base = [f"var(--series-{number})" for number in range(1, 7)]
    if index < len(base):
        return base[index]
    first = index % 6
    second = (index * 5 + 3) % 6
    if first == second:
        second = (second + 1) % 6
    ratio = 35 + (index * 13) % 46
    return f"color-mix(in srgb, {base[first]} {ratio}%, {base[second]})"


def _standalone_html(body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Plasmid evidence report</title>
<style>
:root{{color-scheme:light dark;--bg:light-dark(#fff,#111827);--fg:light-dark(#17202b,#edf2f7);--muted:light-dark(#566273,#abb5c4);--border:light-dark(#cbd3dd,#3d4858);--series-1:light-dark(#075fc7,#64a7ff);--series-2:light-dark(#087f5b,#48d6a4);--series-3:light-dark(#b64e08,#ff9a45);--series-4:light-dark(#7a42c7,#bb8cff);--series-5:light-dark(#a00d49,#ff6da8);--series-6:light-dark(#937100,#e2bd37)}}
*{{box-sizing:border-box}}body{{margin:24px auto;padding:0 18px;max-width:1240px;background:var(--bg);color:var(--fg);font:14px/1.45 ui-sans-serif,system-ui,sans-serif}}h1{{margin:0;font-size:24px}}h2{{font-size:15px;margin:0 0 6px}}.sub,.muted{{color:var(--muted);overflow-wrap:anywhere}}code{{overflow-wrap:anywhere;white-space:normal}}a{{color:var(--series-1)}}
.metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:16px 0}}.metrics div,.flow article{{border:1px solid var(--border);padding:10px;min-width:0}}.metrics strong{{display:block;font-size:19px}}.metrics span{{display:block}}.flow{{display:grid;grid-template-columns:1fr 36px 1fr 36px 1fr;align-items:stretch;gap:6px}}.flow article.source{{border-top:4px solid var(--series-1)}}.flow article.calculated{{border-top:4px solid var(--series-2)}}.flow article.external{{border-top:4px solid var(--series-4)}}.flow p{{margin:0}}.arrow{{display:grid;place-items:center;font-size:22px;color:var(--muted)}}
.map{{border:1px solid var(--border);padding:8px;margin:10px 0}}svg{{display:block;width:100%;height:auto}}svg text{{fill:var(--fg);font-size:10px}}.tabs{{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 8px}}button{{flex:0 0 auto;max-width:100%;padding:7px 10px;background:transparent;color:var(--fg);border:1px solid var(--border);cursor:pointer}}button[aria-pressed="true"]{{border-color:var(--series-1);box-shadow:inset 0 -2px 0 var(--series-1)}}[data-panel-content][hidden]{{display:none}}.notice{{border-left:4px solid var(--series-4);padding:7px 10px;color:var(--muted)}}
.table-wrap{{width:100%;overflow:auto;max-height:560px;border:1px solid var(--border)}}table{{width:100%;border-collapse:collapse;min-width:900px}}table.wide{{min-width:1380px}}th,td{{padding:7px;text-align:left;vertical-align:top;border-bottom:1px solid var(--border)}}thead th{{position:sticky;top:0;background:var(--bg);z-index:1}}td ul{{margin:0;padding-left:18px}}.swatch{{display:inline-block;width:10px;height:10px;margin-right:6px}}details{{border:1px solid var(--border);padding:8px 10px;margin:8px 0}}summary{{cursor:pointer;font-weight:600}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.chips{{display:flex;flex-wrap:wrap;gap:5px}}.chips span,.chip{{border:1px solid var(--border);padding:2px 5px}}
@media(max-width:720px){{.metrics{{grid-template-columns:repeat(2,minmax(0,1fr))}}.flow{{grid-template-columns:1fr}}.arrow{{transform:rotate(90deg);min-height:20px}}}}@media(max-width:420px){{.metrics{{grid-template-columns:1fr}}body{{margin-top:16px}}}}
</style></head><body>{body}</body></html>"""


def _mapping_list(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_int_mapping(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): int(count) for key, count in value.items() if isinstance(count, int)
    }


def _script_json(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _json_details(value: object) -> str:
    payload = _esc(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))
    return f"<details><summary>View</summary><pre>{payload}</pre></details>"


def _plannotate_location(row: Mapping[str, Any]) -> str:
    start = row.get("start location")
    end = row.get("end location")
    return f"{start}–{end}" if start is not None and end is not None else "—"


def _percent(value: object) -> str:
    try:
        return f"{float(str(value)):.3g}%"
    except (TypeError, ValueError):
        return "—"


def _swatch(color: str) -> str:
    return f'<i class="swatch" style="background:{color}"></i>'


def _chip_list(values: Sequence[str]) -> str:
    return (
        " ".join(f'<span class="chip">{_esc(value)}</span>' for value in values) or "—"
    )


def _empty_row(columns: int, text: str) -> str:
    return f'<tr><td colspan="{columns}" class="muted">{_esc(text)}</td></tr>'


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)
