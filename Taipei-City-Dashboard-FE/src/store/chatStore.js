import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import http from "../router/axios";

export const useChatStore = defineStore('chat', () => {
  	// 預設訊息
  	const defaultChatData = [
    	{
      		id: 1,
      		role: 'bot',
	  		isDefault: true,
      		content:
        	'您好，我是【臺北城市儀表板】小幫手，很高興為您服務！\n 您可以： \n\n • 點擊左側既有的儀表板主題，快速查看各主題內容 \n • 輸入您感興趣的主題描述，我會自動為您組建最適合的儀表板 \n\n 如果有想了解的內容，歡迎直接告訴我，我會盡力協助！\n\n 📩 聯絡信箱：tuic@gov.taipei \n 🏢 臺北大數據中心 \n\n',
    	},
  	];

	const recommendComponents = ref(null)

  	// 從 sessionStorage 讀取
  	const savedChatData = JSON.parse(sessionStorage.getItem('chatData')) || [];

  	// 拼接預設訊息 + sessionStorage 的聊天紀錄
  	const chatData = ref([...defaultChatData, ...savedChatData]);

  	// 監聽 chatData 的變化，自動同步到 sessionStorage
  	watch(
    	chatData,
    	(newVal) => {
      	// 只存使用者與機器人的聊天訊息，不存重複的預設訊息
      	const userBotMessages = newVal.filter((item) => !item.isDefault)
      	sessionStorage.setItem('chatData', JSON.stringify(userBotMessages))
    	},
    	{ deep: true }
  	);

  	const addChatData = (newChatData) => {
    	chatData.value.push({ id: chatData.value.length + 1, isDefault: false, ...newChatData });
  	};

	const buildSessionId = () => {
		const d = new Date();
		const todayId =
			d.getFullYear() +
			String(d.getMonth() + 1).padStart(2, "0") +
			String(d.getDate()).padStart(2, "0");

		return "session_" + todayId;
	};

	const buildMessages = () => {
		return chatData.value
			.filter((m) => !m.isDefault && (m.role === "user" || m.role === "bot"))
			.map((m) => ({
				role: m.role === "bot" ? "assistant" : "user",
				content: m.content,
			}));
	};
	
	const dedupeComponents = (components) => {
		return Array.from(
			components.reduce((map, item) => {
				const key = item.index;
				const exist = map.get(key);

				if (!exist || item.city === "metrotaipei") {
					map.set(key, item);
				}

				return map;
			}, new Map()).values(),
		);
	};

  	const addQueryData = async (newChatData) => {

    	chatData.value.push({ id: chatData.value.length + 1, isDefault: false, ...newChatData });

		recommendComponents.value = [];

		try {
			const response = await http.post("/ai/chat/twai", {
				session: buildSessionId(),
				messages: buildMessages(),
			});
			const aiData = response.data?.data;
			const aiContent = aiData?.content || "很抱歉，目前無法產生回覆，請稍後再試。";
			const components = Array.isArray(aiData?.components) ? aiData.components : [];
			recommendComponents.value = dedupeComponents(components);
			const topK = [...recommendComponents.value].sort(
				(a, b) => (Number(b.score) || 0) - (Number(a.score) || 0),
			);

			chatData.value.push({
				id: chatData.value.length + 1,
				role: "bot",
				isDefault: false,
				button: topK.length > 0 ? [{ id: 1, text: "建立儀表板" }] : null,
				content: aiContent,
				relations: topK.length > 0 ? topK : null,
			});

			if (aiData?.tool_used === true) {
				await saveChatLog(newChatData.content, recommendComponents.value);
			}

		} catch (error) {
			console.error("AiChatError :", error);
			chatData.value.push({
				id: chatData.value.length + 1,
				role: "bot",
				isDefault: false,
				content: "很抱歉，目前無法完成查詢，請稍後再試。",
			});
		}
  	};

	const saveChatLog = async(question, answer) => {
		try {
        	const formData = new FormData();
        	const d = new Date();
        	const todayId =
          		d.getFullYear() +
          		String(d.getMonth() + 1).padStart(2, "0") +
          		String(d.getDate()).padStart(2, "0");

        	formData.append("session", "session_" + todayId);
        	formData.append("question", question);
        	formData.append("answer", JSON.stringify(answer));

        	await http.post("/chatlog/", formData, {
          		headers: {
            		"Content-Type": "multipart/form-data",
          		},
        	});
      	} catch (error) {
        	console.error("saveChatLog error:", error);
      	}
	};

	return { chatData, addChatData, addQueryData, saveChatLog }
})
