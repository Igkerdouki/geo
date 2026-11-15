"""Deterministic exports from a saved packet, never another AI rewrite."""
from io import BytesIO
import json
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

DIRECTORY='https://www.cdfa.ca.gov/exec/county/county_contacts.html'
REPORTING='https://www.cdpr.ca.gov/report-a-pesticide-incident/'


def inquiry(packet):
    c=packet['context'];loc=c['location'];county=packet['county'].title()
    return {'authority':f'{county} County Agricultural Commissioner','directory_url':DIRECTORY,'reporting_url':REPORTING,
      'subject':f'Request for clarification: pesticide-use records near {loc["name"]}',
      'body':f'''Dear {county} County Agricultural Commissioner’s Office,

I am requesting clarification about agricultural pesticide-use records near {loc['name']} ({loc['lat']:.5f}, {loc['lon']:.5f}).

I reviewed an AskGaia evidence report covering {c['start_year']}-{c['end_year']} within a {c['radius_km']:g} km search radius. The report is based on CDPR records and identifies limitations, including section-level locations and incomplete evidence where sources were unavailable. Report reference: {packet['id']}, created {packet['created_at']}.

Could you clarify the coverage and location precision of those records, whether more detailed public records are available, and which office can address questions about nearby applications and school notification information?

Historical use and hypothetical simulations do not establish current spraying, personal exposure, or a health effect. I am asking for information, not making an allegation.

Source: https://www.cdpr.ca.gov/pesticide-use-in-california/
Authority directory: {DIRECTORY}

Thank you,
[Your name and preferred contact information]'''}


def evidence_text(e):
    r=e['result'];name=e['tool']
    if e['status']!='complete':return ['Unavailable: no result inferred.']
    if name=='pur_records':
        return [f"Reported use: {r.get('total_lbs',0):,} lb; {r.get('chemicals_found',0)} chemicals in the selected window."]+[f"{v['name']}: {v['lbs']:,} lb across {v.get('sections','?')} sections." for v in r.get('top_chemicals',[])]+[r.get('note','')]
    if name=='environmental_trends':return [f"{v['year']}: {v['reported_lbs']:,.2f} lb ({v['rows']:,} reporting rows)." for v in r.get('years',[])]+[r.get('scope',''),f"Missing years: {r.get('missing_years',[])}. Missing is not zero."]
    if name=='wind_conditions':return [f"Wind from {r.get('from_deg')} degrees at {r.get('speed_ms')} m/s; valid {r.get('valid_at_utc')}.",r.get('kind','Weather-model estimate, not a local sensor.')]
    if name=='nearby_schools':return [f"{s['name']} ({s['lat']:.5f}, {s['lon']:.5f})" for s in r.get('schools',[])]+[r.get('scope','')]
    if name=='map_simulation':return [f"Scenario {r['id']}; status {r['status']}.",f"Source: {r['scenario']['source_lat']:.5f}, {r['scenario']['source_lon']:.5f}; wind from {r['scenario']['direction']:g} degrees at {r['scenario']['speed']:g} m/s; assumed stability {r['scenario']['stability']}.",r.get('normalization','No field for calm wind.')]+r.get('limitations',[])
    # Small chemical profiles are retained exactly, with annotation provenance explicit.
    lines=['Local profile annotations; verify current classifications with the publisher.']
    for match in r.get('matches',[]):
        lines.append(f"{match['name']} (CDPR code {match['chem_code']})")
        lines.extend(f"{key.replace('_',' ').capitalize()}: {value}" for key,value in match.items() if key not in {'name','chem_code'})
    return lines


def render_pdf(packet):
    buffer=BytesIO();styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='GaiaBody',fontName='Helvetica',fontSize=9,leading=13,spaceAfter=6,textColor=colors.HexColor('#213b34'),wordWrap='CJK'))
    styles['Title'].textColor=colors.HexColor('#154e3c')
    styles['Heading2'].textColor=colors.HexColor('#154e3c')
    flow=[]
    def p(text,style='GaiaBody'):return Paragraph(escape(str(text)).replace('\n','<br/>'),styles[style])
    def section(title,lines):
        flow.append(p(title,'Heading2'))
        for line in lines:
            if line:flow.append(p(line))
    c=packet['context'];loc=c['location']
    flow.extend([p('AskGaia','Title'),p('Environmental evidence report','Heading1'),p(loc['name'],'Heading2'),p(f"Coordinates: {loc['lat']:.5f}, {loc['lon']:.5f} | {packet['county'].title()} County"),p(f"Historical window: {c['start_year']}-{c['end_year']} | Search radius: {c['radius_km']:g} km"),p(f"Generated: {packet['created_at']} | Evidence status: {packet['status']}"),p(f"Report ID: {packet['id']}")])
    section('What this report can establish',packet['limitations'])
    for index,e in enumerate(packet['evidence'],1):
        title=e['tool'].replace('_',' ').title()
        section(f'{index}. {title} [{e["id"]}]',evidence_text(e))
        source=e.get('source',{})
        flow.append(p(f"Source: {source.get('name','Unavailable')} | {source.get('url','')}"))
        flow.append(p('Retrieved: '+e.get('retrieved_at',packet['created_at'])))
        flow.append(Spacer(1,7))
    section('Next steps',[f"For questions about pesticide-use records, consult the {packet['county'].title()} County Agricultural Commissioner.",DIRECTORY,'Review the companion inquiry draft before sending. No message has been sent.','Saved reports are snapshots. Later data updates do not change this report.'])
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#52675f'))
        canvas.drawString(42,25,'AskGaia | Recorded use, modelled scenarios, and uncertainty kept distinct')
        canvas.drawRightString(A4[0]-42,25,str(doc.page))
    SimpleDocTemplate(buffer,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=45,title='AskGaia environmental evidence report',author='AskGaia').build(flow,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()
