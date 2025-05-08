// Next.js (App Router) + shadcn/ui + 企业知识问答 Chat 界面模板
// 目录结构: app/page.tsx  (首页)

'use client';

import { useState } from 'react';
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2 } from "lucide-react";

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function HomePage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim()) return;

    const newMessages = [...messages, { role: 'user', content: input }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: input }),
    });

    if (!response.body) {
      setLoading(false);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let assistantMessage = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      assistantMessage += decoder.decode(value);
      setMessages((msgs) => [
        ...newMessages,
        { role: 'assistant', content: assistantMessage },
      ]);
    }

    setLoading(false);
  };

  return (
    <div className="max-w-2xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">企业知识问答系统</h1>
      <Card className="h-[500px] flex flex-col">
        <CardContent className="flex-1 overflow-hidden">
          <ScrollArea className="h-full pr-2">
            {messages.map((msg, idx) => (
              <div key={idx} className={`my-2 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                <span className="block p-2 rounded bg-muted inline-block max-w-[80%]">
                  {msg.content}
                </span>
              </div>
            ))}
            {loading && <Loader2 className="animate-spin mx-auto text-gray-400" />}
          </ScrollArea>
        </CardContent>
        <div className="flex items-center border-t p-2 gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="请输入问题..."
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          />
          <Button onClick={handleSend} disabled={loading}>
            发送
          </Button>
        </div>
      </Card>
    </div>
  );
}
