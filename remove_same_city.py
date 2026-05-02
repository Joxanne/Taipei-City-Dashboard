import re

path = 'c:/碩士/Hackathon/Taipei-City-Dashboard/Taipei-City-Dashboard-FE/src/dashboardComponent/components/BusTransferChart.vue'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'const sameCity = computed\([\s\S]*?\);\n', '', content)
content = content.replace('!canSearch.value || !sameCity.value', '!canSearch.value')
content = content.replace('v-if="canSearch && !sameCity"', 'v-if="false"')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done frontend')
