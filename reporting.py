"""CSV/PDF report generation."""
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

def dataframe_csv(df): return df.to_csv(index=False).encode("utf-8")

def business_pdf(title,kpis,findings,limitations):
    buf=BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=36)
    styles=getSampleStyleSheet()
    story=[Paragraph(title,styles["Title"]),Spacer(1,12),Paragraph("Executive summary generated from the supplied Bengaluru restaurant dataset.",styles["BodyText"]),Spacer(1,12)]
    data=[["Metric","Value"]]+[[str(k).replace("_"," ").title(),str(v)] for k,v in kpis.items()]
    t=Table(data,colWidths=[220,220]); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#5b1730")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.grey),("PADDING",(0,0),(-1,-1),6)])); story += [t,Spacer(1,16),Paragraph("Key findings",styles["Heading2"])]
    for f in findings: story += [Paragraph("• "+str(f),styles["BodyText"]),Spacer(1,5)]
    story += [Paragraph("Limitations",styles["Heading2"])]
    for f in limitations: story += [Paragraph("• "+str(f),styles["BodyText"]),Spacer(1,5)]
    doc.build(story); return buf.getvalue()
