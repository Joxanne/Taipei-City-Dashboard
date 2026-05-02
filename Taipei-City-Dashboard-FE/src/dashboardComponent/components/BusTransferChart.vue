<script setup>
import { ref, reactive, computed, watch, onMounted } from "vue";
import http from "../../router/axios";
import SearchableSelect from "./SearchableSelect.vue";

const props = defineProps([
	"chart_config",
	"activeChart",
	"activeCity",
	"series",
]);

const cities = ref([]);
const maxTransfers = ref(1);
const resultLoading = ref(false);
const resultError = ref("");
const directRoutes = ref([]);
const transferRoutes = ref([]);
const showSql = ref(false);

const validDistricts = {
	taipei: ["中正區", "大同區", "中山區", "松山區", "大安區", "萬華區", "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區"],
	newtaipei: ["板橋區", "三重區", "中和區", "永和區", "新莊區", "新店區", "樹林區", "鶯歌區", "三峽區", "淡水區", "汐止區", "瑞芳區", "土城區", "蘆洲區", "五股區", "泰山區", "林口區", "深坑區", "石碇區", "坪林區", "三芝區", "石門區", "八里區", "平溪區", "雙溪區", "貢寮區", "金山區", "萬里區", "烏來區"]
};

function createSelectionState() {
	return reactive({
		city: "",
		district: "",
		road: "",
		stopId: "",
		districts: [],
		roads: [],
		stops: [],
		loading: false,
	});
}

const fromState = createSelectionState();
const toState = createSelectionState();

const canSearch = computed(
	() => fromState.stopId && toState.stopId && fromState.city && toState.city,
);

function resetRoutesAndStops(state) {
	state.road = "";
	state.stopId = "";
	state.roads = [];
	state.stops = [];
}

function resetStops(state) {
	state.stopId = "";
	state.stops = [];
}

async function fetchCities() {
	try {
		const res = await http.get("/bus/lookup/cities");
		cities.value = res.data.data ?? [];
	} catch {
		cities.value = [];
	}
}

async function fetchDistricts(state) {
	state.loading = true;
	try {
		const res = await http.get("/bus/lookup/districts", {
			params: { city: state.city },
		});
		let rawDistricts = res.data.data ?? [];
		if (validDistricts[state.city]) {
			rawDistricts = rawDistricts.filter(d => validDistricts[state.city].includes(d));
		}
		state.districts = rawDistricts;
	} catch {
		state.districts = [];
	} finally {
		state.loading = false;
	}
}

async function fetchRoads(state) {
	state.loading = true;
	try {
		const res = await http.get("/bus/lookup/roads", {
			params: { city: state.city, district: state.district },
		});
		state.roads = res.data.data ?? [];
	} catch {
		state.roads = [];
	} finally {
		state.loading = false;
	}
}

async function fetchStops(state) {
	state.loading = true;
	try {
		const res = await http.get("/bus/lookup/stops-by-road", {
			params: {
				city: state.city,
				district: state.district,
				road: state.road,
			},
		});
		
		const rawStops = res.data.data ?? [];
		const seen = new Set();
		state.stops = rawStops.filter(s => {
			if (seen.has(s.stop_name)) return false;
			seen.add(s.stop_name);
			return true;
		});

	} catch {
		state.stops = [];
	} finally {
		state.loading = false;
	}
}

function clearResults() {
	directRoutes.value = [];
	transferRoutes.value = [];
	resultError.value = "";
}

async function fetchTransfers() {
	if (!canSearch.value) {
		clearResults();
		return;
	}
	resultLoading.value = true;
	resultError.value = "";
	try {
		const res = await http.get("/bus/transfer", {
			params: {
				city: fromState.city,
				from_stop: fromState.stopId,
				to_stop: toState.stopId,
				max_transfers: maxTransfers.value,
			},
		});
		directRoutes.value = res.data.data?.direct_routes ?? [];
		transferRoutes.value = res.data.data?.transfer_routes ?? [];
	} catch (err) {
		resultError.value = "查詢失敗，請稍後再試";
		clearResults();
	} finally {
		resultLoading.value = false;
	}
}

function routeColor(routeName) {
	if (!routeName) return "#4fc3f7";
	let hash = 0;
	for (let i = 0; i < routeName.length; i += 1) {
		hash = routeName.charCodeAt(i) + ((hash << 5) - hash);
	}
	const hue = Math.abs(hash) % 360;
	return `hsl(${hue}, 70%, 55%)`;
}

const resultCombos = computed(() => {
	const combos = [];
	for (const route of directRoutes.value) {
		if (route?.route_name) {
			combos.push(`搭${route.route_name}可直達`);
		}
	}
	for (const item of transferRoutes.value) {
		if (item?.route_a && item?.route_b) {
			combos.push(`搭${item.route_a}轉${item.route_b}可抵達`);
		}
	}
	return combos;
});

const fromStopName = computed(() => {
	const s = fromState.stops.find(s => s.stop_location_id === fromState.stopId);
	return s?.stop_name ?? fromState.stopId;
});

const toStopName = computed(() => {
	const s = toState.stops.find(s => s.stop_location_id === toState.stopId);
	return s?.stop_name ?? toState.stopId;
});

const sqlPreview = computed(() => {
	if (!canSearch.value) return "";

	const directSql = `-- 直達查詢
SELECT DISTINCT br.route_name
FROM public.bus_route_tpe br
JOIN public.bus_route_stops_tpe brs1
  ON br.route_id = brs1.route_id
 AND br.city = brs1.city
JOIN public.bus_route_stops_tpe brs2
  ON br.route_id = brs2.route_id
JOIN public.bus_stop_tpe bs2
  ON brs2.stop_location_id = bs2.stop_location_id
 AND brs2.city = bs2.city
WHERE brs1.stop_location_id = ${fromState.stopId}
  AND bs2.stop_name = '${toStopName.value}'
ORDER BY br.route_name;`;

	if (maxTransfers.value === 0) return directSql;

	const transferSql = `

-- 一次轉乘查詢
WITH route_a AS (
  SELECT DISTINCT br.route_id, br.route_name, br.city
  FROM public.bus_route_tpe br
  JOIN public.bus_route_stops_tpe brs
    ON br.route_id = brs.route_id AND br.city = brs.city
  WHERE brs.stop_location_id = ${fromState.stopId}
),
route_b AS (
  SELECT DISTINCT br.route_id, br.route_name, br.city
  FROM public.bus_route_tpe br
  JOIN public.bus_route_stops_tpe brs
    ON br.route_id = brs.route_id AND br.city = brs.city
  WHERE brs.stop_location_id = ${toState.stopId}
),
route_a_stops AS (
  SELECT ra.route_id, ra.route_name, ra.city, brs.stop_location_id
  FROM route_a ra
  JOIN public.bus_route_stops_tpe brs
    ON ra.route_id = brs.route_id AND ra.city = brs.city
),
route_b_stops AS (
  SELECT rb.route_id, rb.route_name, rb.city, brs.stop_location_id
  FROM route_b rb
  JOIN public.bus_route_stops_tpe brs
    ON rb.route_id = brs.route_id AND rb.city = brs.city
)
SELECT DISTINCT
  ra.route_name AS route_a,
  rb.route_name AS route_b,
  bs.stop_name,
  bs.district
FROM route_a_stops ra
JOIN route_b_stops rb
  ON ra.stop_location_id = rb.stop_location_id
JOIN public.bus_stop_tpe bs
  ON bs.stop_location_id = ra.stop_location_id
WHERE ra.route_id <> rb.route_id
  AND ra.stop_location_id NOT IN (${fromState.stopId}, ${toState.stopId})
ORDER BY route_a, route_b, bs.stop_name;`;

	return directSql + transferSql;
});

function resolveDefaultCity() {
	if (props.activeCity === "newtaipei") return "newtaipei";
	if (props.activeCity === "taipei" || props.activeCity === "metrotaipei") {
		return "taipei";
	}
	return "";
}

function applyDefaultCity() {
	const defaultCity = resolveDefaultCity();
	if (!defaultCity) return;
	if (!fromState.city) fromState.city = defaultCity;
	if (!toState.city) toState.city = defaultCity;
}

watch(
	() => fromState.city,
	async (next) => {
		resetRoutesAndStops(fromState);
		fromState.district = "";
		fromState.districts = [];
		if (next) await fetchDistricts(fromState);
	},
);

watch(
	() => toState.city,
	async (next) => {
		resetRoutesAndStops(toState);
		toState.district = "";
		toState.districts = [];
		if (next) await fetchDistricts(toState);
	},
);

watch(
	() => fromState.district,
	async (next) => {
		resetRoutesAndStops(fromState);
		if (next && fromState.city) await fetchRoads(fromState);
	},
);

watch(
	() => toState.district,
	async (next) => {
		resetRoutesAndStops(toState);
		if (next && toState.city) await fetchRoads(toState);
	},
);

watch(
	() => fromState.road,
	async (next) => {
		resetStops(fromState);
		if (next && fromState.city && fromState.district) {
			await fetchStops(fromState);
		}
	},
);

watch(
	() => toState.road,
	async (next) => {
		resetStops(toState);
		if (next && toState.city && toState.district) {
			await fetchStops(toState);
		}
	},
);

watch(
	() => [fromState.stopId, toState.stopId, maxTransfers.value],
	() => {
		fetchTransfers();
	},
);

onMounted(() => {
	fetchCities().finally(() => {
		applyDefaultCity();
	});
});

watch(
	() => props.activeCity,
	() => {
		applyDefaultCity();
	},
);
</script>

<template>
	<div class="bus-transfer-chart">
		<div class="btc-selectors">
			<div class="btc-card">
				<div class="btc-card__title">起點 A</div>
				<div class="btc-fields-grid">
					<div class="btc-field">
						<label>城市</label>
						<SearchableSelect v-model="fromState.city" :options="cities" />
					</div>
					<div class="btc-field">
						<label>行政區</label>
						<SearchableSelect v-model="fromState.district" :options="fromState.districts.map(d => ({label:d, value:d}))" :disabled="!fromState.city" />
					</div>
					<div class="btc-field">
						<label>路名</label>
						<SearchableSelect v-model="fromState.road" :options="fromState.roads.map(r => ({label: r.road_name, value: r.road_name}))" :disabled="!fromState.district" />
					</div>
					<div class="btc-field">
						<label>公車站</label>
						<SearchableSelect v-model="fromState.stopId" :options="fromState.stops.map(s => ({label: s.stop_name, value: s.stop_location_id}))" :disabled="!fromState.road" />
					</div>
				</div>
			</div>

			<div class="btc-card">
				<div class="btc-card__title">終點 B</div>
				<div class="btc-fields-grid">
					<div class="btc-field">
						<label>城市</label>
						<SearchableSelect v-model="toState.city" :options="cities" />
					</div>
					<div class="btc-field">
						<label>行政區</label>
						<SearchableSelect v-model="toState.district" :options="toState.districts.map(d => ({label:d, value:d}))" :disabled="!toState.city" />
					</div>
					<div class="btc-field">
						<label>路名</label>
						<SearchableSelect v-model="toState.road" :options="toState.roads.map(r => ({label: r.road_name, value: r.road_name}))" :disabled="!toState.district" />
					</div>
					<div class="btc-field">
						<label>公車站</label>
						<SearchableSelect v-model="toState.stopId" :options="toState.stops.map(s => ({label: s.stop_name, value: s.stop_location_id}))" :disabled="!toState.road" />
					</div>
				</div>
			</div>
		</div>

		<div class="btc-actions">
			<div class="btc-toggle">
				<button
					:class="{ active: maxTransfers === 0 }"
					@click="maxTransfers = 0"
				>
					直達
				</button>
				<button
					:class="{ active: maxTransfers === 1 }"
					@click="maxTransfers = 1"
				>
					一次轉乘
				</button>
			</div>
			<div v-if="false" class="btc-warning">
				起訖站需同一城市
			</div>
		</div>

		<div class="btc-results">
			<div v-if="resultLoading" class="btc-loading">
				<span class="material-icons">sync</span>
				查詢中...
			</div>

			<div v-else-if="!canSearch" class="btc-empty">請先選擇起訖站</div>

			<div v-else-if="resultError" class="btc-error">
				{{ resultError }}
			</div>

			<div v-else class="btc-result-content">
				<div class="btc-section">
					<h4>公車組合</h4>
					<div class="btc-combo-list">
						<div
							v-for="combo in resultCombos"
							:key="combo"
							class="btc-combo-tag"
						>
							{{ combo }}
						</div>
						<div v-if="!resultCombos.length" class="btc-empty">
							目前沒有可行組合
						</div>
					</div>
				</div>
				<div class="btc-section">
					<h4>直達路線</h4>
					<div class="btc-route-list">
						<div
							v-for="route in directRoutes"
							:key="route.route_name"
							class="btc-route-card"
							:style="{
								'--route-color': routeColor(route.route_name),
							}"
						>
							<span class="btc-route-badge">直達</span>
							<span class="btc-route-name">
								{{ route.route_name }}
							</span>
						</div>
						<div v-if="!directRoutes.length" class="btc-empty">
							目前沒有直達路線
						</div>
					</div>
				</div>

				<div v-if="maxTransfers === 1" class="btc-section">
					<h4>一次轉乘</h4>
					<div class="btc-transfer-list">
						<div
							v-for="(item, index) in transferRoutes"
							:key="`${item.route_a}-${item.route_b}-${index}`"
							class="btc-transfer-card"
						>
							<div class="btc-transfer-flow">
								<div class="btc-node">A</div>
								<div
									class="btc-line"
									:style="{
										'--route-color': routeColor(
											item.route_a,
										),
									}"
								/>
								<div class="btc-node btc-node--transfer">T</div>
								<div
									class="btc-line"
									:style="{
										'--route-color': routeColor(
											item.route_b,
										),
									}"
								/>
								<div class="btc-node">B</div>
							</div>
							<div class="btc-transfer-info">
								<div
									class="btc-route-pill"
									:style="{
										'--route-color': routeColor(
											item.route_a,
										),
									}"
								>
									{{ item.route_a }}
								</div>
								<div class="btc-transfer-stop">
									轉乘站：{{ item.transfer_stop.stop_name }}
								</div>
								<div
									class="btc-route-pill"
									:style="{
										'--route-color': routeColor(
											item.route_b,
										),
									}"
								>
									{{ item.route_b }}
								</div>
							</div>
						</div>
						<div v-if="!transferRoutes.length" class="btc-empty">
							目前沒有一次轉乘建議
						</div>
					</div>
				</div>
			</div>
		</div>

		<div v-if="canSearch" class="btc-sql-block">
			<button class="btc-sql-toggle" @click="showSql = !showSql">
				<span class="material-icons">{{ showSql ? 'expand_less' : 'code' }}</span>
				{{ showSql ? '隱藏 SQL' : '顯示 SQL' }}
			</button>
			<pre v-if="showSql" class="btc-sql-pre">{{ sqlPreview }}</pre>
		</div>
	</div>
</template>

<style scoped lang="scss">
.bus-transfer-chart {
	position: absolute;
	top: 0; left: 0; right: 0; bottom: 0;
	display: flex;
	overflow-y: auto;
	padding-right: 4px;
	flex-direction: column;
	gap: 12px;
}

.bus-transfer-chart * {
	
}

.btc-selectors {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
	gap: 12px;
	flex-shrink: 0;
}

.btc-card {
	padding: 12px;
	border-radius: 10px;
	background: linear-gradient(
		135deg,
		rgba(40, 52, 71, 0.9),
		rgba(25, 33, 45, 0.9)
	);
	border: 1px solid rgba(71, 89, 110, 0.6);
	box-shadow: 0 8px 18px rgba(0, 0, 0, 0.25);
}

.btc-card__title {
	font-size: 14px;
	font-weight: 600;
	color: #e5edf7;
	margin-bottom: 8px;
}

.btc-fields-grid {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 8px 12px;
}

.btc-field {
	display: flex;
	flex-direction: column;
	gap: 4px;

	label {
		font-size: 12px;
		color: #9fb0c6;
	}
}

.btc-select {
	background: rgba(18, 26, 38, 0.9);
	border: 1px solid rgba(69, 90, 115, 0.8);
	border-radius: 8px;
	color: #d8e2f0;
	padding: 6px 8px;
	font-size: 13px;
	outline: none;
	transition: border-color 0.15s;

	&:focus {
		border-color: #43d0ff;
	}

	&:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
}

.btc-actions {
	display: flex;
	align-items: center;
	justify-content: space-between;
	flex-shrink: 0;
}

.btc-toggle {
	display: flex;
	background: rgba(20, 28, 40, 0.9);
	border-radius: 999px;
	padding: 4px;
	gap: 4px;

	button {
		border: none;
		background: transparent;
		color: #9fb0c6;
		padding: 6px 12px;
		border-radius: 999px;
		font-size: 12px;
		cursor: pointer;
		transition: all 0.15s;

		&.active {
			background: linear-gradient(120deg, #2f80ed, #56ccf2);
			color: #0b1625;
			font-weight: 600;
		}
	}
}

.btc-warning {
	font-size: 12px;
	color: #ffb74d;
}

.btc-results {
	flex: 1;
	overflow-y: auto;
	min-height: 0;
	background: rgba(17, 24, 34, 0.6);
	border: 1px solid rgba(71, 89, 110, 0.3);
	border-radius: 12px;
	padding: 12px;
}

.btc-loading {
	display: flex;
	align-items: center;
	gap: 8px;
	color: #b6c4d9;
	font-size: 13px;

	span {
		animation: spin 1s linear infinite;
	}
}

.btc-result-content {
	display: flex;
	flex-direction: column;
	gap: 16px;
}

.btc-section h4 {
	font-size: 14px;
	color: #e5edf7;
	margin-bottom: 8px;
}

.btc-route-list {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
	gap: 10px;
}

.btc-combo-list {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
}

.btc-combo-tag {
	padding: 6px 10px;
	border-radius: 999px;
	background: rgba(67, 208, 255, 0.15);
	border: 1px solid rgba(67, 208, 255, 0.5);
	color: #cfefff;
	font-size: 12px;
	font-weight: 600;
}

.btc-route-card {
	padding: 10px;
	border-radius: 10px;
	background: linear-gradient(
		140deg,
		rgba(20, 30, 45, 0.95),
		rgba(13, 20, 31, 0.95)
	);
	border: 1px solid color-mix(in srgb, var(--route-color) 60%, #0f1723 40%);
	box-shadow: 0 6px 14px rgba(0, 0, 0, 0.2);
}

.btc-route-badge {
	display: inline-block;
	font-size: 11px;
	padding: 2px 6px;
	border-radius: 999px;
	background: color-mix(in srgb, var(--route-color) 70%, #0f1723 30%);
	color: #0f1723;
	font-weight: 700;
}

.btc-route-name {
	display: block;
	margin-top: 6px;
	font-size: 14px;
	font-weight: 600;
	color: #dfe9f7;
}

.btc-transfer-list {
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.btc-transfer-card {
	background: rgba(16, 24, 36, 0.9);
	border: 1px solid rgba(80, 98, 120, 0.5);
	border-radius: 12px;
	padding: 12px;
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.btc-transfer-flow {
	display: flex;
	align-items: center;
	gap: 8px;
}

.btc-node {
	width: 28px;
	height: 28px;
	border-radius: 50%;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 12px;
	font-weight: 700;
	background: #1d2a3c;
	color: #d9e5f2;
	border: 1px solid rgba(94, 116, 145, 0.6);
}

.btc-node--transfer {
	background: #273249;
	color: #ffc857;
	border-color: rgba(255, 200, 87, 0.6);
}

.btc-line {
	flex: 1;
	height: 4px;
	border-radius: 999px;
	background: var(--route-color);
}

.btc-transfer-info {
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: 8px;
}

.btc-route-pill {
	padding: 4px 10px;
	border-radius: 999px;
	background: color-mix(in srgb, var(--route-color) 70%, #0f1723 30%);
	color: #0f1723;
	font-weight: 700;
	font-size: 12px;
}

.btc-transfer-stop {
	font-size: 12px;
	color: #cbd7e6;
}

.btc-empty,
.btc-error {
	font-size: 13px;
	color: #8fa4bd;
	text-align: center;
	padding: 12px 0;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.btc-sql-block {
	flex-shrink: 0;
}

.btc-sql-toggle {
	display: flex;
	align-items: center;
	gap: 6px;
	background: transparent;
	border: 1px solid rgba(71, 89, 110, 0.5);
	border-radius: 8px;
	color: #7a9bb8;
	font-size: 12px;
	padding: 6px 12px;
	cursor: pointer;
	transition: color 0.15s, border-color 0.15s;

	&:hover {
		color: #b6d4ef;
		border-color: rgba(71, 89, 110, 0.9);
	}

	.material-icons {
		font-size: 16px;
	}
}

.btc-sql-pre {
	margin-top: 8px;
	padding: 12px;
	background: rgba(10, 16, 25, 0.85);
	border: 1px solid rgba(55, 72, 95, 0.6);
	border-radius: 8px;
	color: #7ecfff;
	font-size: 12px;
	font-family: 'Fira Code', 'Consolas', monospace;
	line-height: 1.6;
	white-space: pre;
	overflow-x: auto;
}
</style>
