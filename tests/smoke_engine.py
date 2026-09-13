# -*- coding: utf-8 -*-
"""Quick end-to-end test of the renderer engine without GUI."""

import os, zipfile, re
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from docxforge.engine.schema import (
    create_project, Project, TemplateConfig, FieldMapping, FieldType,
    CycleMapping, AggregationMapping, AggregationFunction,
)
from docxforge.engine.template_parser import scan_template
from docxforge.engine.renderer import Renderer
from docxforge.engine.data_reader import DataReader

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def main():
    create_project('tests/test_project')
    print('1. Project created')

    result = scan_template('tests/test_project/Шаблоны/договор_поставки.docx')
    names = [p[0] for p in result['placeholders']]
    print(f'2. Template scan: {len(names)} placeholders')

    prj = Project()
    tc = TemplateConfig()
    tc.fields['организация'] = FieldMapping(type=FieldType.CONSTANT, value='ООО Ромашка')
    tc.fields['должность_поставщика'] = FieldMapping(type=FieldType.TABLE, file='сотрудники.xlsx', column='должность')
    tc.fields['фио_поставщика'] = FieldMapping(type=FieldType.TABLE, file='сотрудники.xlsx', column='фио', linked_to='должность_поставщика')
    tc.fields['название_клиента'] = FieldMapping(type=FieldType.TABLE, file='клиенты.xlsx', column='название')
    tc.fields['должность_клиента'] = FieldMapping(type=FieldType.TABLE, file='клиенты.xlsx', column='должность', linked_to='название_клиента')
    tc.fields['фио_клиента'] = FieldMapping(type=FieldType.TABLE, file='клиенты.xlsx', column='фио', linked_to='название_клиента')
    tc.fields['ИНН_клиента'] = FieldMapping(type=FieldType.TABLE, file='клиенты.xlsx', column='ИНН', linked_to='название_клиента')
    tc.fields['адрес_клиента'] = FieldMapping(type=FieldType.TABLE, file='клиенты.xlsx', column='адрес', linked_to='название_клиента')
    tc.fields['doc_number'] = FieldMapping(type=FieldType.COUNTER, start=1, format='0001')
    tc.cycles.append(CycleMapping(table='спецификация.xlsx', columns={'наименование':'наименование','количество':'количество','цена':'цена'}))
    tc.aggregations['итого'] = AggregationMapping(function=AggregationFunction.SUM, table='спецификация.xlsx', column='цена')
    tc.aggregations['с_ндс'] = AggregationMapping(function=AggregationFunction.SUM_MULTIPLY, table='спецификация.xlsx', column='цена', multiplier=1.2)
    prj.templates['договор_поставки.docx'] = tc
    prj.to_file('tests/test_project/проект.docxforge')
    print('3. Config saved')

    reader = DataReader()
    renderer = Renderer('tests/test_project', reader)
    renderer.load_project()
    outputs = renderer.render('договор_поставки.docx', {})
    print(f'4. Output: {len(outputs)} files')

    with zipfile.ZipFile(outputs[0], 'r') as zf:
        doc_xml = etree.parse(zf.open('word/document.xml'))
        all_text = []
        for p in doc_xml.findall('.//{%s}p' % W):
            texts = [t.text or '' for t in p.findall('.//{%s}t' % W)]
            if texts:
                all_text.append(''.join(texts))
        text = '\n'.join(all_text)

        remaining = re.findall(r'\{\{.+?\}\}', text)
        print(f'5. Remaining placeholders: {len(remaining)}')

        if not remaining or all('image:' in r for r in remaining):
            print('   (only image: placeholders remain — expected, v2 feature)')

        checks = [
            ('ООО Ромашка', 'ООО Ромашка' in text),
            ('ООО Альфа', 'ООО Альфа' in text),
            ('ИНН 7712345678', '7712345678' in text),
            ('Ген. директор', 'Ген. директор' in text),
            ('Иванов И.И.', 'Иванов И.И.' in text),
            ('Товар А (цикл)', 'Товар А' in text),
            ('Товар Б (цикл)', 'Товар Б' in text),
            ('Товар В (цикл)', 'Товар В' in text),
            ('Итого 8000', '8000' in text),
            ('С НДС 9600', '9600' in text),
        ]
        all_ok = True
        for name, ok in checks:
            s = '✅' if ok else '❌'
            if not ok:
                all_ok = False
            print(f'   {s} {name}')
        print()
        if all_ok:
            print('✅ ALL CHECKS PASSED — engine is working!')
        else:
            print('❌ SOME CHECKS FAILED')

if __name__ == '__main__':
    main()
