// "use client";

// import { useEffect, useState } from "react";
// import { AgentPanel } from "@/components/agent-panel";
// import { Chat } from "@/components/chat";
// import type { Agent, AgentEvent, GuardrailCheck, Message } from "@/lib/types";
// import { callChatAPI } from "@/lib/api";

// export default function Home() {
//   const [messages, setMessages] = useState<Message[]>([]);
//   const [events, setEvents] = useState<AgentEvent[]>([]);
//   const [agents, setAgents] = useState<Agent[]>([]);
//   const [currentAgent, setCurrentAgent] = useState<string>("");
//   const [guardrails, setGuardrails] = useState<GuardrailCheck[]>([]);
//   const [context, setContext] = useState<Record<string, any>>({});
//   const [conversationId, setConversationId] = useState<string | null>(null);
//   // Loading state while awaiting assistant response
//   const [isLoading, setIsLoading] = useState(false);

//   // Boot the conversation
//   useEffect(() => {
//     (async () => {
//       const data = await callChatAPI("", conversationId ?? "");
//       setConversationId(data.conversation_id);
//       setCurrentAgent(data.current_agent);
//       setContext(data.context);
//       const initialEvents = (data.events || []).map((e: any) => ({
//         ...e,
//         timestamp: e.timestamp ?? Date.now(),
//       }));
//       setEvents(initialEvents);
//       setAgents(data.agents || []);
//       setGuardrails(data.guardrails || []);
//       if (Array.isArray(data.messages)) {
//         setMessages(
//           data.messages.map((m: any) => ({
//             id: Date.now().toString() + Math.random().toString(),
//             content: m.content,
//             role: "assistant",
//             agent: m.agent,
//             timestamp: new Date(),
//           }))
//         );
//       }
//     })();
//   }, []);

//   // Send a user message
//   const handleSendMessage = async (content: string) => {
//     const userMsg: Message = {
//       id: Date.now().toString(),
//       content,
//       role: "user",
//       timestamp: new Date(),
//     };

//     setMessages((prev) => [...prev, userMsg]);
//     setIsLoading(true);

//     const data = await callChatAPI(content, conversationId ?? "");

//     if (!conversationId) setConversationId(data.conversation_id);
//     setCurrentAgent(data.current_agent);
//     setContext(data.context);
//     if (data.events) {
//       const stamped = data.events.map((e: any) => ({
//         ...e,
//         timestamp: e.timestamp ?? Date.now(),
//       }));
//       setEvents((prev) => [...prev, ...stamped]);
//     }
//     if (data.agents) setAgents(data.agents);
//     // Update guardrails state
//     if (data.guardrails) setGuardrails(data.guardrails);

//     if (data.messages) {
//       const responses: Message[] = data.messages.map((m: any) => ({
//         id: Date.now().toString() + Math.random().toString(),
//         content: m.content,
//         role: "assistant",
//         agent: m.agent,
//         timestamp: new Date(),
//       }));
//       setMessages((prev) => [...prev, ...responses]);
//     }

//     setIsLoading(false);
//   };

//   return (
//     <main className="flex h-screen gap-2 bg-gray-100 p-2">
//       <AgentPanel
//         agents={agents}
//         currentAgent={currentAgent}
//         events={events}
//         guardrails={guardrails}
//         context={context}
//       />
//       <Chat
//         messages={messages}
//         onSendMessage={handleSendMessage}
//         isLoading={isLoading}
//       />
//     </main>
//   );
// }























"use client";

import { useEffect, useState } from "react";
// Correcting import paths from alias to relative paths
import { AgentPanel } from "../components/agent-panel";
import { Chat } from "../components/Chat";
import type { Agent, AgentEvent, GuardrailCheck, Message } from "@/lib/types"; // This type import might still depend on local setup. Assuming for now it's fine or handled elsewhere.
import { callChatAPI } from "../lib/api";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string>("");
  const [guardrails, setGuardrails] = useState<GuardrailCheck[]>([]);
  const [context, setContext] = useState<Record<string, any>>({});
  const [conversationId, setConversationId] = useState<string | null>(null);
  // Loading state while awaiting assistant response
  const [isLoading, setIsLoading] = useState(false);

  // Boot the conversation
  useEffect(() => {
    (async () => {
      // Fetch initial chat data
      const data = await callChatAPI("", conversationId ?? "");

      // Check if data is valid before processing
      if (!data) {
        console.error("Initial chat API call returned no data.");
        // Optionally, show an error message to the user
        setMessages([{
          id: Date.now().toString(),
          content: "Failed to load chat. Please check backend or API key.",
          role: "assistant",
          agent: "System",
          timestamp: new Date(),
        }]);
        return;
      }

      setConversationId(data.conversation_id || null);
      setCurrentAgent(data.current_agent || "");
      setContext(data.context || {});
      
      const initialEvents = (data.events || []).map((e: any) => ({
        ...e,
        timestamp: e.timestamp ?? Date.now(),
      }));
      setEvents(initialEvents);
      setAgents(data.agents || []);
      setGuardrails(data.guardrails || []);
      
      if (Array.isArray(data.messages)) {
        setMessages(
          data.messages.map((m: any) => ({
            id: Date.now().toString() + Math.random().toString(),
            content: m.content,
            role: "assistant",
            agent: m.agent,
            timestamp: new Date(),
          }))
        );
      }
    })();
  }, []); // Empty dependency array means this runs once on mount

  // Send a user message
  const handleSendMessage = async (content: string) => {
    const userMsg: Message = {
      id: Date.now().toString(),
      content,
      role: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    // Call the chat API with user message
    const data = await callChatAPI(content, conversationId ?? "");

    // Check if data is valid before processing
    if (!data) {
      console.error("Chat API call returned no data for message:", content);
      setMessages((prev) => [...prev, {
        id: Date.now().toString(),
        content: "Oops! I couldn't get a response. Please try again later or check your API quota.",
        role: "assistant",
        agent: "System",
        timestamp: new Date(),
      }]);
      setIsLoading(false);
      return;
    }

    if (!conversationId) setConversationId(data.conversation_id || null);
    setCurrentAgent(data.current_agent || "");
    setContext(data.context || {});
    
    if (data.events) {
      const stamped = data.events.map((e: any) => ({
        ...e,
        timestamp: e.timestamp ?? Date.now(),
      }));
      setEvents((prev) => [...prev, ...stamped]);
    }
    if (data.agents) setAgents(data.agents);
    // Update guardrails state
    if (data.guardrails) setGuardrails(data.guardrails);

    if (data.messages) {
      const responses: Message[] = data.messages.map((m: any) => ({
        id: Date.now().toString() + Math.random().toString(),
        content: m.content,
        role: "assistant",
        agent: m.agent,
        timestamp: new Date(),
      }));
      setMessages((prev) => [...prev, ...responses]);
    }

    setIsLoading(false);
  };

  return (
    <main className="flex h-screen gap-2 bg-gray-100 p-2">
      <AgentPanel
        agents={agents}
        currentAgent={currentAgent}
        events={events}
        guardrails={guardrails}
        context={context}
      />
      <Chat
        messages={messages}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
      />
    </main>
  );
}
