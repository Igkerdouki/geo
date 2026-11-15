/**
 * AI Assistant - Embedded chat for pesticide questions
 *
 * Users can ask about:
 * - Chemical dangers and safety
 * - Areas with high exposure
 * - Latest spraying in their area
 * - Health effects
 * - Regulations
 */

import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from './workflowClient.mjs'
import {
  MessageCircle, Send, X, Bot, User, Loader,
  AlertTriangle, Info, Droplets, MapPin, Clock,
  HelpCircle, Sparkles, ChevronDown
} from 'lucide-react'



// Predefined quick questions
const QUICK_QUESTIONS = [
  "What is Chlorpyrifos and is it dangerous?",
  "Which county has the highest pesticide use?",
  "What schools are near pesticide zones?",
  "What are the health effects of glyphosate?",
  "When was the last spray in Kern County?",
  "How does wind affect pesticide drift?"
]

export default function AIAssistant({ isOpen, onClose }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `Hi! I'm the Geo AI Assistant. I can help you with:

- **Chemical information** - Understanding recorded pesticide use
- **Location data** - Spray history for specific counties
- **Health effects** - Questions that need verified sources
- **Drift scenarios** - How weather affects transport

What would you like to know?`
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const processQuestion = async question => {
    const response = await api('/chat', {method:'POST', body:JSON.stringify({
      message:question, history:messages.slice(-12).map(({role,content})=>({role,content:content.slice(0,6000)}))
    })})
    return [response.answer, ...(response.sources || []).map(s=>'Source: '+s), ...(response.warnings || [])].join('\n\n')
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await processQuestion(input)
      setMessages(prev => [...prev, { role: 'assistant', content: response }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: err.message || "Chat unavailable. Please try again."
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleQuickQuestion = (question) => {
    setInput(question)
  }

  if (!isOpen) return null

  return (
    <motion.div
      className="ai-assistant-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div
        className="ai-assistant"
        initial={{ y: 50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
      >
        {/* Header */}
        <div className="ai-header">
          <div className="ai-title">
            <Sparkles size={20} />
            <span>Geo AI Assistant</span>
          </div>
          <button className="ai-close" onClick={onClose}><X size={20} /></button>
        </div>

        {/* Messages */}
        <div className="ai-messages">
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              className={`ai-message ${msg.role}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <div className="message-avatar">
                {msg.role === 'assistant' ? <Bot size={18} /> : <User size={18} />}
              </div>
              <div className="message-content" dangerouslySetInnerHTML={{
                __html: msg.content
                  .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                  .replace(/\n/g, '<br/>')
              }} />
            </motion.div>
          ))}

          {loading && (
            <div className="ai-message assistant">
              <div className="message-avatar"><Bot size={18} /></div>
              <div className="message-content typing">
                <Loader className="spin" size={16} /> Thinking...
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Questions */}
        <div className="quick-questions">
          <div className="quick-label"><HelpCircle size={14} /> Quick questions:</div>
          <div className="quick-buttons">
            {QUICK_QUESTIONS.slice(0, 3).map((q, i) => (
              <button key={i} onClick={() => handleQuickQuestion(q)}>
                {q.length > 30 ? q.slice(0, 30) + '...' : q}
              </button>
            ))}
          </div>
        </div>

        {/* Input */}
        <div className="ai-input-area">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask about chemicals, locations, health effects..."
            disabled={loading}
          />
          <button onClick={handleSend} disabled={loading || !input.trim()}>
            <Send size={18} />
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}
