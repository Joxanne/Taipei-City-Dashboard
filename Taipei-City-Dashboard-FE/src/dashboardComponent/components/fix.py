import re

with open('c:/碩士/Hackathon/Taipei-City-Dashboard/Taipei-City-Dashboard-FE/src/dashboardComponent/components/BusTransferChart.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Import SearchableSelect
content = content.replace('import http from "../../router/axios";', 'import http from "../../router/axios";\nimport SearchableSelect from "./SearchableSelect.vue";')

# 2. Add Deduplication in fetchStops
dedup_code = '''
		const rawStops = res.data.data ?? [];
		const seen = new Set();
		state.stops = rawStops.filter(s => {
			if (seen.has(s.stop_name)) return false;
			seen.add(s.stop_name);
			return true;
		});
'''
content = content.replace('state.stops = res.data.data ?? [];', dedup_code)

# 3. Fix CSS Overflow
content = content.replace('overflow: visible;', '')

# 4. Replace <select> with <SearchableSelect>
# Cities
content = re.sub(r'<select v-model="fromState.city" class="btc-select">.*?</select>', 
                 '<SearchableSelect v-model="fromState.city" :options="cities" />', content, flags=re.DOTALL)
content = re.sub(r'<select v-model="toState.city" class="btc-select">.*?</select>', 
                 '<SearchableSelect v-model="toState.city" :options="cities" />', content, flags=re.DOTALL)

# Districts
content = re.sub(r'<select[^>]*v-model="fromState.district"[^>]*>.*?</select>',
                 '<SearchableSelect v-model="fromState.district" :options="fromState.districts.map(d => ({label:d, value:d}))" :disabled="!fromState.city" />', content, flags=re.DOTALL)
content = re.sub(r'<select[^>]*v-model="toState.district"[^>]*>.*?</select>',
                 '<SearchableSelect v-model="toState.district" :options="toState.districts.map(d => ({label:d, value:d}))" :disabled="!toState.city" />', content, flags=re.DOTALL)

# Roads
content = re.sub(r'<select[^>]*v-model="fromState.road"[^>]*>.*?</select>',
                 '<SearchableSelect v-model="fromState.road" :options="fromState.roads.map(r => ({label: r.road_name, value: r.road_name}))" :disabled="!fromState.district" />', content, flags=re.DOTALL)
content = re.sub(r'<select[^>]*v-model="toState.road"[^>]*>.*?</select>',
                 '<SearchableSelect v-model="toState.road" :options="toState.roads.map(r => ({label: r.road_name, value: r.road_name}))" :disabled="!toState.district" />', content, flags=re.DOTALL)

# Stops
content = re.sub(r'<select[^>]*v-model="fromState.stopId"[^>]*>.*?</select>',
                 '<SearchableSelect v-model="fromState.stopId" :options="fromState.stops.map(s => ({label: s.stop_name, value: s.stop_location_id}))" :disabled="!fromState.road" />', content, flags=re.DOTALL)
content = re.sub(r'<select[^>]*v-model="toState.stopId"[^>]*>.*?</select>',
                 '<SearchableSelect v-model="toState.stopId" :options="toState.stops.map(s => ({label: s.stop_name, value: s.stop_location_id}))" :disabled="!toState.road" />', content, flags=re.DOTALL)

with open('c:/碩士/Hackathon/Taipei-City-Dashboard/Taipei-City-Dashboard-FE/src/dashboardComponent/components/BusTransferChart.vue', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
