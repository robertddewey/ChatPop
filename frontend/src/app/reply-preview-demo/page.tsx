'use client';

import React, { useState } from 'react';
import { Reply, X } from 'lucide-react';

export default function ReplyPreviewDemoPage() {
  const [isDarkMode, setIsDarkMode] = useState(false);

  const sampleReply = {
    username: "DiamondGrove695",
    content: "This is the message content you're replying to - it shows a preview here"
  };

  // Define different style variations for reply preview bar
  const styles = {
    // LIGHT MODE STYLES
    light: [
      {
        name: "Clean Gray Border (Current Default)",
        container: "flex items-center justify-between px-4 py-2 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700",
        icon: "w-4 h-4 flex-shrink-0 text-blue-500",
        username: "text-xs font-semibold text-gray-700 dark:text-gray-300",
        content: "text-xs text-gray-600 dark:text-gray-400 truncate",
        closeButton: "p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded",
        closeIcon: "w-4 h-4 text-gray-500"
      },
      {
        name: "White Card with Shadow",
        container: "flex items-center justify-between px-4 py-3 bg-white border-b-2 border-gray-300 shadow-sm",
        icon: "w-4 h-4 flex-shrink-0 text-blue-600",
        username: "text-sm font-bold text-gray-900",
        content: "text-xs text-gray-600 truncate",
        closeButton: "p-1.5 hover:bg-gray-100 rounded-full transition-colors",
        closeIcon: "w-4 h-4 text-gray-600"
      },
      {
        name: "Blue Accent Border",
        container: "flex items-center justify-between px-4 py-2 bg-blue-50 border-l-4 border-blue-500",
        icon: "w-4 h-4 flex-shrink-0 text-blue-600",
        username: "text-xs font-semibold text-blue-900",
        content: "text-xs text-blue-700 truncate",
        closeButton: "p-1 hover:bg-blue-200 rounded",
        closeIcon: "w-4 h-4 text-blue-600"
      },
      {
        name: "Minimal Line",
        container: "flex items-center justify-between px-3 py-2 bg-white border-b border-gray-300",
        icon: "w-3.5 h-3.5 flex-shrink-0 text-gray-500",
        username: "text-xs font-medium text-gray-800",
        content: "text-xs text-gray-500 truncate",
        closeButton: "p-0.5 hover:bg-gray-200 rounded",
        closeIcon: "w-4 h-4 text-gray-400"
      },
      {
        name: "Purple Gradient",
        container: "flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-purple-50 to-pink-50 border-b-2 border-purple-300",
        icon: "w-4 h-4 flex-shrink-0 text-purple-600",
        username: "text-sm font-bold text-purple-900",
        content: "text-xs text-purple-700 truncate",
        closeButton: "p-1 hover:bg-purple-200 rounded-full",
        closeIcon: "w-4 h-4 text-purple-600"
      },
      {
        name: "Frosted Glass",
        container: "flex items-center justify-between px-4 py-2 bg-white/80 backdrop-blur-sm border-b border-gray-200/50",
        icon: "w-4 h-4 flex-shrink-0 text-gray-600",
        username: "text-xs font-semibold text-gray-900",
        content: "text-xs text-gray-600 truncate",
        closeButton: "p-1 hover:bg-white/90 rounded",
        closeIcon: "w-4 h-4 text-gray-500"
      }
    ],

    // DARK MODE STYLES
    dark: [
      {
        name: "Dark Zinc (Current Default)",
        container: "flex items-center justify-between px-4 py-2 bg-zinc-800 border-b border-zinc-700",
        icon: "w-4 h-4 flex-shrink-0 text-cyan-400",
        username: "text-xs font-semibold text-zinc-100",
        content: "text-xs text-zinc-300 truncate",
        closeButton: "p-1 hover:bg-zinc-700 rounded",
        closeIcon: "w-4 h-4 text-zinc-400"
      },
      {
        name: "Black with Cyan Accent",
        container: "flex items-center justify-between px-4 py-3 bg-black border-b-2 border-cyan-500 shadow-lg",
        icon: "w-4 h-4 flex-shrink-0 text-cyan-400",
        username: "text-sm font-bold text-white",
        content: "text-xs text-gray-300 truncate",
        closeButton: "p-1.5 hover:bg-zinc-900 rounded-full transition-colors",
        closeIcon: "w-4 h-4 text-cyan-400"
      },
      {
        name: "Cyan Glow Border",
        container: "flex items-center justify-between px-4 py-2 bg-zinc-900 border-l-4 border-cyan-500",
        icon: "w-4 h-4 flex-shrink-0 text-cyan-400",
        username: "text-xs font-semibold text-cyan-100",
        content: "text-xs text-cyan-200 truncate",
        closeButton: "p-1 hover:bg-cyan-900/30 rounded",
        closeIcon: "w-4 h-4 text-cyan-400"
      },
      {
        name: "Minimal Dark Line",
        container: "flex items-center justify-between px-3 py-2 bg-zinc-900 border-b border-zinc-700",
        icon: "w-3.5 h-3.5 flex-shrink-0 text-gray-400",
        username: "text-xs font-medium text-gray-200",
        content: "text-xs text-gray-400 truncate",
        closeButton: "p-0.5 hover:bg-zinc-800 rounded",
        closeIcon: "w-4 h-4 text-gray-500"
      },
      {
        name: "Purple Dark Gradient",
        container: "flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-purple-900/50 to-pink-900/50 border-b-2 border-purple-500",
        icon: "w-4 h-4 flex-shrink-0 text-purple-400",
        username: "text-sm font-bold text-purple-100",
        content: "text-xs text-purple-200 truncate",
        closeButton: "p-1 hover:bg-purple-800/50 rounded-full",
        closeIcon: "w-4 h-4 text-purple-300"
      },
      {
        name: "Frosted Dark Glass",
        container: "flex items-center justify-between px-4 py-2 bg-black/60 backdrop-blur-sm border-b border-white/10",
        icon: "w-4 h-4 flex-shrink-0 text-gray-300",
        username: "text-xs font-semibold text-white",
        content: "text-xs text-gray-300 truncate",
        closeButton: "p-1 hover:bg-white/10 rounded",
        closeIcon: "w-4 h-4 text-gray-400"
      }
    ]
  };

  const currentStyles = isDarkMode ? styles.dark : styles.light;

  return (
    <div className={`min-h-screen ${isDarkMode ? 'bg-zinc-900' : 'bg-gray-50'}`}>
      {/* Header */}
      <div className={`border-b ${isDarkMode ? 'bg-zinc-800 border-zinc-700' : 'bg-white border-gray-200'} sticky top-0 z-10`}>
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                Reply Preview Bar Theme Demo
              </h1>
              <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                Choose your preferred reply preview style - appears above text input when replying
              </p>
            </div>
            <button
              onClick={() => setIsDarkMode(!isDarkMode)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                isDarkMode
                  ? 'bg-cyan-500 hover:bg-cyan-600 text-white'
                  : 'bg-purple-600 hover:bg-purple-700 text-white'
              }`}
            >
              {isDarkMode ? '🌙 Dark Mode' : '☀️ Light Mode'}
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="space-y-6">
          {currentStyles.map((style, index) => (
            <div key={index} className={`rounded-xl overflow-hidden ${isDarkMode ? 'bg-zinc-800' : 'bg-white'} shadow-lg`}>
              <div className="p-6">
                <h2 className={`text-lg font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  Style {index + 1}: {style.name}
                </h2>
              </div>

              {/* Live Preview of Reply Preview Bar */}
              <div className={style.container}>
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <Reply className={style.icon} />
                  <div className="flex-1 min-w-0">
                    <div className={style.username}>
                      Replying to {sampleReply.username}
                    </div>
                    <div className={style.content}>
                      {sampleReply.content}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  className={style.closeButton}
                  aria-label="Cancel reply"
                >
                  <X className={style.closeIcon} />
                </button>
              </div>

              {/* Simulated Input Area Below */}
              <div className={`px-4 py-3 ${isDarkMode ? 'bg-zinc-900' : 'bg-gray-100'} border-t ${isDarkMode ? 'border-zinc-700' : 'border-gray-200'}`}>
                <div className={`flex gap-2 items-center px-3 py-2 rounded-lg ${isDarkMode ? 'bg-zinc-800 text-gray-300' : 'bg-white text-gray-600'}`}>
                  <span className="text-sm">Type your message...</span>
                </div>
              </div>

              {/* Style details */}
              <details className="p-6 pt-0">
                <summary className={`cursor-pointer text-sm font-medium ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} hover:underline`}>
                  View CSS Classes
                </summary>
                <div className={`mt-2 p-3 rounded text-xs font-mono ${isDarkMode ? 'bg-zinc-900 text-gray-300' : 'bg-gray-50 text-gray-700'} overflow-x-auto`}>
                  <div className="space-y-2">
                    <div><strong>Container:</strong> <br/>{style.container}</div>
                    <div><strong>Icon:</strong> {style.icon}</div>
                    <div><strong>Username:</strong> {style.username}</div>
                    <div><strong>Content:</strong> {style.content}</div>
                    <div><strong>Close Button:</strong> {style.closeButton}</div>
                    <div><strong>Close Icon:</strong> {style.closeIcon}</div>
                  </div>
                </div>
              </details>
            </div>
          ))}
        </div>

        {/* Database Fields Reference */}
        <div className={`mt-12 p-6 rounded-xl ${isDarkMode ? 'bg-zinc-800' : 'bg-white'} shadow-lg`}>
          <h2 className={`text-lg font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
            Database Fields
          </h2>
          <p className={`text-sm mb-4 ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>
            These styles map to the following ChatTheme database fields:
          </p>
          <div className={`space-y-2 text-sm ${isDarkMode ? 'text-gray-300' : 'text-gray-700'} font-mono`}>
            <div><span className="text-blue-500">reply_preview_container</span> - Outer container with background/border</div>
            <div><span className="text-blue-500">reply_preview_icon</span> - Reply arrow icon (↩️)</div>
            <div><span className="text-blue-500">reply_preview_username</span> - "Replying to {'{username}'}" text</div>
            <div><span className="text-blue-500">reply_preview_content</span> - Message preview text</div>
            <div><span className="text-blue-500">reply_preview_close_button</span> - X button to cancel reply</div>
            <div><span className="text-blue-500">reply_preview_close_icon</span> - X icon styling</div>
          </div>
        </div>

        {/* Design Considerations */}
        <div className={`mt-6 p-6 rounded-xl ${isDarkMode ? 'bg-zinc-800' : 'bg-white'} shadow-lg`}>
          <h2 className={`text-lg font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
            Design Considerations
          </h2>
          <ul className={`space-y-2 text-sm ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>
            <li className="flex items-start gap-2">
              <span className="text-green-500 font-bold">✓</span>
              <span><strong>Location:</strong> Appears above text input when replying to a message</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 font-bold">✓</span>
              <span><strong>Visibility:</strong> Should stand out but not overwhelm the chat interface</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 font-bold">✓</span>
              <span><strong>Truncation:</strong> Content truncates to prevent overflow on long messages</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 font-bold">✓</span>
              <span><strong>Clickability:</strong> Close button (X) should have clear hover state</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 font-bold">✓</span>
              <span><strong>Context:</strong> Username and content preview help user remember what they're replying to</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 font-bold">✓</span>
              <span><strong>Spacing:</strong> 2px gap (mt-2) between reply preview and input form recommended</span>
            </li>
          </ul>
        </div>

        {/* Implementation Guide */}
        <div className={`mt-6 p-6 rounded-xl ${isDarkMode ? 'bg-zinc-800' : 'bg-white'} shadow-lg`}>
          <h2 className={`text-lg font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
            Implementation Guide
          </h2>
          <p className={`text-sm mb-3 ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>
            To update reply preview styling in the database:
          </p>
          <div className={`p-4 rounded ${isDarkMode ? 'bg-zinc-900' : 'bg-gray-50'}`}>
            <code className={`text-xs ${isDarkMode ? 'text-gray-300' : 'text-gray-700'} block whitespace-pre-wrap`}>
{`./venv/bin/python manage.py shell -c "
from chats.models import ChatTheme
theme = ChatTheme.objects.get(theme_id='dark-mode')
theme.reply_preview_container = 'flex items-center justify-between px-4 py-2 bg-zinc-800 border-b border-zinc-700'
theme.reply_preview_icon = 'w-4 h-4 flex-shrink-0 text-cyan-400'
theme.reply_preview_username = 'text-xs font-semibold text-zinc-100'
theme.reply_preview_content = 'text-xs text-zinc-300 truncate'
theme.reply_preview_close_button = 'p-1 hover:bg-zinc-700 rounded'
theme.reply_preview_close_icon = 'w-4 h-4 text-zinc-400'
theme.save()
print('Updated reply preview styling')
"`}</code>
          </div>
        </div>
      </div>
    </div>
  );
}
