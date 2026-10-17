import csv
import io
from xml.sax.saxutils import escape
from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .db import engine, TABLES
from .service import validate, public
from .security import log

def import_csv(resource,content,user):
    if resource not in ('creators','videos'): raise HTTPException(422,'Импорт разрешён для авторов и видео')
    if len(content.encode())>200000: raise HTTPException(413,'CSV слишком большой; максимум 200 КиБ')
    reader=csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
    if not reader.fieldnames: raise HTTPException(422,'Нет заголовка CSV')
    rows=list(reader)
    if len(rows)>1000: raise HTTPException(422,'Импортируйте до 1000 строк за раз')
    values=[]
    for index,row in enumerate(rows,2):
        try: values.append(validate(resource,{k:v for k,v in row.items() if v not in ('',None)}))
        except HTTPException as error: raise HTTPException(422,f'Строка {index}: {error.detail}')
    inserted=0;duplicates=0
    with engine.begin() as c:
        for data in values:
            try:
                with c.begin_nested():
                    item=c.execute(TABLES[resource].insert().values(**data).returning(TABLES[resource].c.id)).scalar_one()
                    log(c,user,'import',resource,item)
                inserted+=1
            except IntegrityError as error:
                if getattr(error.orig,'sqlstate',None)=='23505': duplicates+=1
                else: raise HTTPException(422,'Проверьте обязательные поля и ID связанных записей; импорт отменён')
    return {'inserted':inserted,'duplicates_skipped':duplicates}

def export_report(kind,days):
    from .service import analytics
    from .db import settings
    with engine.connect() as c:
        data=analytics(c,days)
        report_note=c.scalar(select(settings.c.value).where(settings.c.name=='report_note')) or ''
    columns=['name','clicks','joins','leaves','conversion','spend','cost_per_subscriber']
    headers=['Кампания','Переходы','Вступления','Выходы','Конверсия %','Расходы (все)','Цена подписчика']
    rows=[[row.get(col) for col in columns] for row in data['campaigns']]
    disclaimer=f'Период: {days} дней. Переходы — запросы, вступления — полученные события. Расходы — за всё время.'
    if report_note: disclaimer+=' '+report_note[:1000]
    if kind=='xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        wb=Workbook(); ws=wb.active; ws.title='Кампании';ws.append(headers)
        for row in rows:
            ws.append([("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for v in row])
        for cell in ws[1]: cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='151D2D')
        for column in 'ABCDEFG': ws.column_dimensions[column].width=22
        ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions;ws.append([]);ws.append([disclaimer])
        buf=io.BytesIO();wb.save(buf)
        return Response(buf.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename=analytics.xlsx'})
    if kind=='pdf':
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont('DejaVu','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        style=ParagraphStyle('ru',fontName='DejaVu',fontSize=8,leading=12)
        buf=io.BytesIO();doc=SimpleDocTemplate(buf,pagesize=landscape(A4),rightMargin=25,leftMargin=25)
        matrix=[[Paragraph(escape(x),style) for x in headers]]+[[Paragraph(escape('Нет данных' if x is None else str(x)),style) for x in row] for row in rows]
        table=Table(matrix,colWidths=[170,85,85,85,85,85,110],repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e2e8f0')),('GRID',(0,0),(-1,-1),0.3,colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        doc.build([Paragraph('TikTok Traffic Admin — аналитика',style),Spacer(1,12),Paragraph(escape(disclaimer),style),Spacer(1,16),table])
        return Response(buf.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename=analytics.pdf'})
    raise HTTPException(404,'Формат не поддерживается')
