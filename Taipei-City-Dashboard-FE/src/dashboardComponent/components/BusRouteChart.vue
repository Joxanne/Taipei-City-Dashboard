<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import http from "../../router/axios";

const props = defineProps([
	"chart_config",
	"activeChart",
	"activeCity",
	"series",
	"map_config",
	"map_filter",
	"map_filter_on",
]);

const emits = defineEmits(["filterByParam", "clearByParamFilter"]);

// ── State ──────────────────────────────────────────────────────────────────────
const stops = ref([]);
const selectedRoute = ref("");
const search = ref("");
const dropdownOpen = ref(false);
const loading = ref(false);
const selectorRef = ref(null);
const dropdownRef = ref(null);
const dropdownStyle = ref({});
const mapFilterActive = ref(false);

let latestRequestId = 0;

const STOPS_PER_ROW = 6;

// ── Routes from series ─────────────────────────────────────────────────────────
const allRoutes = computed(() => {
	if (!props.series?.[0]?.data?.length) return [];
	return props.series[0].data.map((item) => item.x).filter(Boolean);
});

const filteredRoutes = computed(() => {
	if (!search.value) return allRoutes.value;
	return allRoutes.value.filter((r) =>
		r.toLowerCase().includes(search.value.toLowerCase()),
	);
});

// ── Snake layout ───────────────────────────────────────────────────────────────
const stopRows = computed(() => {
	const rows = [];
	for (let i = 0; i < stops.value.length; i += STOPS_PER_ROW) {
		rows.push(
			stops.value.slice(i, i + STOPS_PER_ROW).map((s, j) => ({
				...s,
				globalIdx: i + j,
			})),
		);
	}
	return rows;
});

// ── Gradient #2979FF → #00BFA5 ────────────────────────────────────────────────
function getStopColor(globalIdx) {
	const total = stops.value.length - 1;
	const t = total > 0 ? globalIdx / total : 0;
	const r = Math.round(0x29 + t * (0x00 - 0x29));
	const g = Math.round(0x79 + t * (0xbf - 0x79));
	const b = Math.round(0xff + t * (0xa5 - 0xff));
	return `rgb(${r},${g},${b})`;
}

// ── API ────────────────────────────────────────────────────────────────────────
async function fetchStops(routeName) {
	if (!routeName) return;
	const requestId = ++latestRequestId;
	loading.value = true;
	try {
		const city = props.activeCity || "taipei";
		const res = await http.get("/bus/stops", {
			params: { route: routeName, city },
		});
		if (requestId === latestRequestId) {
			stops.value = res.data.data ?? [];
		}
	} catch {
		if (requestId === latestRequestId) {
			stops.value = [];
		}
	} finally {
		if (requestId === latestRequestId) {
			loading.value = false;
		}
	}
}

function selectRoute(routeName) {
	selectedRoute.value = routeName;
	search.value = "";
	dropdownOpen.value = false;
	fetchStops(routeName);
	if (props.map_filter && props.map_filter_on) {
		emits("filterByParam", props.map_filter, props.map_config, routeName, null);
		mapFilterActive.value = true;
	}
}

function clearAllRoutes() {
	mapFilterActive.value = false;
	if (props.map_config) {
		emits("clearByParamFilter", props.map_config);
	}
}

// ── Dropdown positioning (Teleport to body) ────────────────────────────────────
function updateDropdownPosition() {
	if (!selectorRef.value) return;
	const rect = selectorRef.value.getBoundingClientRect();
	dropdownStyle.value = {
		position: "fixed",
		top: `${rect.bottom + 4}px`,
		left: `${rect.left}px`,
		width: `${rect.width}px`,
		zIndex: 9999,
	};
}

function toggleDropdown() {
	dropdownOpen.value = !dropdownOpen.value;
	if (dropdownOpen.value) {
		search.value = "";
		updateDropdownPosition();
	}
}

function closeDropdown() {
	dropdownOpen.value = false;
}

function handleViewportChange() {
	if (dropdownOpen.value) updateDropdownPosition();
}

// Click-outside: close when clicking outside both selector AND teleported dropdown
function handleDocumentClick(e) {
	if (
		selectorRef.value?.contains(e.target) ||
		dropdownRef.value?.contains(e.target)
	)
		return;
	closeDropdown();
}

// ── Init ───────────────────────────────────────────────────────────────────────
function initFromSeries() {
	if (allRoutes.value.length) {
		selectedRoute.value = allRoutes.value[0];
		fetchStops(allRoutes.value[0]);
	}
}

watch(allRoutes, (next) => {
	if (next.length) {
		selectedRoute.value = next[0];
		fetchStops(next[0]);
	}
});

onMounted(() => {
	document.addEventListener("click", handleDocumentClick);
	window.addEventListener("resize", handleViewportChange);
	window.addEventListener("scroll", handleViewportChange, true);
	initFromSeries();
});

onUnmounted(() => {
	document.removeEventListener("click", handleDocumentClick);
	window.removeEventListener("resize", handleViewportChange);
	window.removeEventListener("scroll", handleViewportChange, true);
	if (mapFilterActive.value && props.map_config) {
		emits("clearByParamFilter", props.map_config);
	}
});
</script>

<template>
	<div v-if="activeChart === 'BusRouteChart'" class="bus-route-chart">
		<!-- ── Selector display ───────────────────────────────────────────── -->
		<div class="brc-selector-row">
			<div ref="selectorRef" class="brc-selector">
				<div class="brc-selector__display" @click="toggleDropdown">
					<span class="brc-selector__value">{{
						selectedRoute || "—"
					}}</span>
					<span class="material-icons brc-selector__arrow">
						{{ dropdownOpen ? "expand_less" : "expand_more" }}
					</span>
				</div>
			</div>
			<button
				v-if="mapFilterActive && map_filter_on"
				class="brc-show-all"
				@click="clearAllRoutes"
			>
				<span class="material-icons">layers</span>
				顯示全部
			</button>
		</div>

		<!-- ── Dropdown list (teleported to body to escape overflow) ─────── -->
		<Teleport to="body">
			<div
				v-show="dropdownOpen"
				ref="dropdownRef"
				class="brc-dropdown-portal"
				:style="dropdownStyle"
			>
				<input
					v-model="search"
					class="brc-dp__search"
					placeholder="搜尋路線…"
					@click.stop
				/>
				<div class="brc-dp__list">
					<div
						v-for="r in filteredRoutes"
						:key="r"
						class="brc-dp__item"
						:class="{ active: r === selectedRoute }"
						@click="selectRoute(r)"
					>
						{{ r }}
					</div>
					<div v-if="!filteredRoutes.length" class="brc-dp__empty">
						無符合路線
					</div>
				</div>
			</div>
		</Teleport>

		<!-- ── Scrollable content ─────────────────────────────────────────── -->
		<div class="brc-content">
			<div v-if="loading" class="brc-loading">
				<span class="material-icons brc-loading__icon">sync</span>
			</div>

			<div v-else-if="stops.length" class="brc-snake">
				<div
					v-for="(row, ri) in stopRows"
					:key="ri"
					class="brc-snake__section"
				>
					<div
						class="brc-row"
						:class="{ 'brc-row--reverse': ri % 2 === 1 }"
					>
						<div
							class="brc-row__line"
							:style="{
								background: `linear-gradient(to ${ri % 2 === 0 ? 'right' : 'left'},
                  ${getStopColor(ri * STOPS_PER_ROW)},
                  ${getStopColor(Math.min((ri + 1) * STOPS_PER_ROW - 1, stops.length - 1))})`,
							}"
						/>
						<div
							v-for="stop in row"
							:key="stop.stop_seq"
							class="brc-stop"
							:title="`${stop.stop_name}${stop.district ? '（' + stop.district + '）' : ''}`"
						>
							<div
								class="brc-stop__dot"
								:style="{
									backgroundColor: getStopColor(
										stop.globalIdx,
									),
								}"
							/>
							<span class="brc-stop__label">{{
								stop.stop_name
							}}</span>
						</div>
					</div>

					<div
						v-if="ri < stopRows.length - 1"
						class="brc-bend"
						:class="
							ri % 2 === 0 ? 'brc-bend--right' : 'brc-bend--left'
						"
						:style="{
							background: getStopColor(
								Math.min(
									(ri + 1) * STOPS_PER_ROW - 1,
									stops.length - 1,
								),
							),
						}"
					/>
				</div>
			</div>

			<div v-else-if="!loading && selectedRoute" class="brc-empty">
				無去程站牌資料
			</div>
		</div>
	</div>
</template>

<style scoped lang="scss">
.bus-route-chart {
	display: flex;
	flex-direction: column;
	gap: 8px;
	padding: 4px 2px;
	height: 100%;
}

/* ── Selector row ─────────────────────────────────────────────────────────── */
.brc-selector-row {
	display: flex;
	gap: 6px;
	align-items: stretch;
	flex-shrink: 0;
}

/* ── Selector ─────────────────────────────────────────────────────────────── */
.brc-selector {
	flex: 1;
	min-width: 0;
}

.brc-selector__display {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 6px 10px;
	background: var(--color-component-background, #1e2a38);
	border: 1px solid var(--color-border, #2d3e50);
	border-radius: 6px;
	cursor: pointer;
	user-select: none;
	transition: border-color 0.15s;

	&:hover {
		border-color: #2979ff;
	}
}

.brc-selector__value {
	font-size: 14px;
	font-weight: 600;
	color: var(--color-text, #cfd8e3);
	letter-spacing: 0.5px;
}

.brc-selector__arrow {
	font-size: 18px;
	color: var(--color-text-secondary, #8a9bb0);
}

/* ── Show-all button ──────────────────────────────────────────────────────── */
.brc-show-all {
	display: flex;
	align-items: center;
	gap: 4px;
	padding: 6px 10px;
	background: rgba(41, 121, 255, 0.12);
	border: 1px solid rgba(41, 121, 255, 0.4);
	border-radius: 6px;
	color: #2979ff;
	font-size: 12px;
	font-weight: 600;
	cursor: pointer;
	white-space: nowrap;
	transition: background 0.15s, border-color 0.15s;
	flex-shrink: 0;

	.material-icons {
		font-size: 16px;
	}

	&:hover {
		background: rgba(41, 121, 255, 0.22);
		border-color: #2979ff;
	}
}

/* ── Scrollable snake area ────────────────────────────────────────────────── */
.brc-content {
	flex: 1;
	overflow-y: auto;
	min-height: 0;
}

/* ── Loading ──────────────────────────────────────────────────────────────── */
.brc-loading {
	display: flex;
	justify-content: center;
	padding: 24px 0;
}

.brc-loading__icon {
	font-size: 28px;
	color: #2979ff;
	animation: spin 1s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

/* ── Snake layout ─────────────────────────────────────────────────────────── */
.brc-snake {
	display: flex;
	flex-direction: column;
	padding: 4px 0;
}

.brc-snake__section {
	display: flex;
	flex-direction: column;
}

.brc-row {
	display: flex;
	flex-direction: row;
	align-items: flex-start;
	position: relative;
	padding: 0 4px;

	&--reverse {
		flex-direction: row-reverse;
	}
}

.brc-row__line {
	position: absolute;
	top: 5px; /* vertically centred on 14px dot: (14-3)/2 ≈ 5px */
	left: calc(100% / 12); /* centre of 1st stop for 6-stop row */
	right: calc(100% / 12); /* centre of last stop */
	height: 3px;
	border-radius: 2px;
	z-index: 0;
}

.brc-stop {
	flex: 1;
	display: flex;
	flex-direction: column;
	align-items: center;
	position: relative;
	z-index: 1;
	cursor: default;
	min-width: 0;
}

.brc-stop__dot {
	width: 14px;
	height: 14px;
	border-radius: 50%;
	border: 2px solid var(--color-border-white, rgba(255, 255, 255, 0.15));
	flex-shrink: 0;
	box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
	transition: transform 0.15s;

	.brc-stop:hover & {
		transform: scale(1.3);
	}
}

.brc-stop__label {
	margin-top: 4px;
	font-size: 9px;
	color: var(--color-text-secondary, #8a9bb0);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	width: 100%;
	text-align: center;
	line-height: 1.3;
	padding: 0 2px;
	box-sizing: border-box;
}

.brc-bend {
	height: 20px;
	width: 3px;
	border-radius: 2px;

	&--right {
		align-self: flex-end;
		margin-right: calc(100% / 12 - 1px);
	}

	&--left {
		align-self: flex-start;
		margin-left: calc(100% / 12 - 1px);
	}
}

/* ── Empty state ──────────────────────────────────────────────────────────── */
.brc-empty {
	text-align: center;
	font-size: 13px;
	color: var(--color-text-secondary, #8a9bb0);
	padding: 20px 0;
}
</style>

<!-- Teleported dropdown styles — not scoped so they apply outside component DOM -->
<style lang="scss">
.brc-dropdown-portal {
	background: var(--color-component-background, #1e2a38);
	border: 1px solid var(--color-border, #2d3e50);
	border-radius: 6px;
	box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);

	.brc-dp__search {
		width: 100%;
		padding: 7px 10px;
		background: transparent;
		border: none;
		border-bottom: 1px solid var(--color-border, #2d3e50);
		color: var(--color-text, #cfd8e3);
		font-size: 13px;
		outline: none;
		box-sizing: border-box;

		&::placeholder {
			color: var(--color-text-secondary, #8a9bb0);
		}
	}

	.brc-dp__list {
		max-height: 200px;
		overflow-y: auto;
	}

	.brc-dp__item {
		padding: 7px 12px;
		font-size: 13px;
		color: var(--color-text, #cfd8e3);
		cursor: pointer;
		transition: background 0.1s;

		&:hover {
			background: rgba(41, 121, 255, 0.12);
		}

		&.active {
			color: #2979ff;
			font-weight: 600;
		}
	}

	.brc-dp__empty {
		padding: 10px 12px;
		font-size: 13px;
		color: var(--color-text-secondary, #8a9bb0);
		text-align: center;
	}
}
</style>
