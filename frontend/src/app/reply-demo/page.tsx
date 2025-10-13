'use client';

import React, { useState } from 'react';
import { Reply } from 'lucide-react';

export default function ReplyDemoPage() {
  const [isDarkMode, setIsDarkMode] = useState(false);

  const sampleReply = {
    username: "DiamondGrove695",
    content: "Test reply"
  };

  const sampleMessage = "Replying";

  // Define different style variations that work in BOTH blue and gray bubbles
  const styles = {
    // LIGHT MODE STYLES
    light: [
      {
        name: "White Card with Shadow",
        myMessage: "mb-2 p-2 rounded-lg bg-white/95 border border-gray-200 cursor-pointer hover:bg-white transition-colors shadow-sm",
        otherMessage: "mb-2 p-2 rounded-lg bg-white border border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors shadow-sm",
        icon: "w-3 h-3 text-blue-600 flex-shrink-0",
        username: "text-xs font-semibold text-gray-900",
        content: "text-xs text-gray-600 truncate"
      },
      {
        name: "Dark Border Left",
        myMessage: "mb-2 p-2 rounded-lg bg-white/90 border-l-3 border-gray-700 cursor-pointer hover:bg-white transition-colors",
        otherMessage: "mb-2 p-2 rounded-lg bg-white border-l-3 border-gray-600 cursor-pointer hover:bg-gray-50 transition-colors",
        icon: "w-3 h-3 text-gray-700 flex-shrink-0",
        username: "text-xs font-semibold text-gray-900",
        content: "text-xs text-gray-700 truncate"
      },
      {
        name: "Frosted Glass",
        myMessage: "mb-2 p-2 rounded-lg bg-white/80 backdrop-blur-sm border border-white/50 cursor-pointer hover:bg-white/90 transition-colors",
        otherMessage: "mb-2 p-2 rounded-lg bg-white/60 backdrop-blur-sm border border-gray-300 cursor-pointer hover:bg-white/80 transition-colors",
        icon: "w-3 h-3 text-gray-600 flex-shrink-0",
        username: "text-xs font-semibold text-gray-900",
        content: "text-xs text-gray-700 truncate"
      },
      {
        name: "Bold Black Border",
        myMessage: "mb-2 p-2 rounded-lg bg-white border-l-4 border-black cursor-pointer hover:shadow-md transition-all",
        otherMessage: "mb-2 p-2 rounded-lg bg-white border-l-4 border-gray-800 cursor-pointer hover:shadow-md transition-all",
        icon: "w-3 h-3 text-black flex-shrink-0",
        username: "text-xs font-bold text-black",
        content: "text-xs text-gray-700 truncate"
      },
      {
        name: "Subtle Gray Card",
        myMessage: "mb-2 p-2 rounded-lg bg-gray-100/90 border border-gray-300 cursor-pointer hover:bg-gray-100 transition-colors",
        otherMessage: "mb-2 p-2 rounded-lg bg-gray-100 border border-gray-300 cursor-pointer hover:bg-gray-200 transition-colors",
        icon: "w-3 h-3 text-gray-600 flex-shrink-0",
        username: "text-xs font-semibold text-gray-900",
        content: "text-xs text-gray-700 truncate"
      },
      {
        name: "Minimal Line",
        myMessage: "mb-2 p-2 rounded-md bg-black/5 border-l-2 border-gray-500 cursor-pointer hover:bg-black/10 transition-colors",
        otherMessage: "mb-2 p-2 rounded-md bg-gray-200 border-l-2 border-gray-500 cursor-pointer hover:bg-gray-300 transition-colors",
        icon: "w-3 h-3 text-gray-600 flex-shrink-0",
        username: "text-xs font-semibold text-gray-800",
        content: "text-xs text-gray-600 truncate"
      }
    ],

    // DARK MODE STYLES
    dark: [
      {
        name: "Dark Card with Border",
        myMessage: "mb-2 p-2 rounded-lg bg-zinc-900/90 border border-zinc-700 cursor-pointer hover:bg-zinc-900 transition-colors",
        otherMessage: "mb-2 p-2 rounded-lg bg-zinc-800 border border-zinc-600 cursor-pointer hover:bg-zinc-700 transition-colors",
        icon: "w-3 h-3 text-cyan-400 flex-shrink-0",
        username: "text-xs font-semibold text-white",
        content: "text-xs text-gray-300 truncate"
      },
      {
        name: "Cyan Accent Border",
        myMessage: "mb-2 p-2 rounded-lg bg-black/50 border-l-3 border-cyan-400 cursor-pointer hover:bg-black/70 transition-colors",
        otherMessage: "mb-2 p-2 rounded-lg bg-zinc-900 border-l-3 border-cyan-500 cursor-pointer hover:bg-zinc-800 transition-colors",
        icon: "w-3 h-3 text-cyan-400 flex-shrink-0",
        username: "text-xs font-semibold text-white",
        content: "text-xs text-gray-300 truncate"
      },
      {
        name: "Frosted Dark Glass",
        myMessage: "mb-2 p-2 rounded-lg bg-black/60 backdrop-blur-sm border border-white/10 cursor-pointer hover:bg-black/70 transition-colors",
        otherMessage: "mb-2 p-2 rounded-lg bg-zinc-800/60 backdrop-blur-sm border border-zinc-600 cursor-pointer hover:bg-zinc-800/80 transition-colors",
        icon: "w-3 h-3 text-gray-300 flex-shrink-0",
        username: "text-xs font-semibold text-white",
        content: "text-xs text-gray-300 truncate"
      },
      {
        name: "High Contrast White Border",
        myMessage: "mb-2 p-2 rounded-lg bg-zinc-900 border-l-4 border-white cursor-pointer hover:shadow-lg hover:shadow-white/20 transition-all",
        otherMessage: "mb-2 p-2 rounded-lg bg-zinc-800 border-l-4 border-gray-200 cursor-pointer hover:shadow-lg transition-all",
        icon: "w-3 h-3 text-white flex-shrink-0",
        username: "text-xs font-bold text-white",
        content: "text-xs text-gray-200 truncate"
      },
      {
        name: "Subtle Zinc Card",
        myMessage: "mb-2 p-2 rounded-lg bg-zinc-800/90 border border-zinc-700 cursor-pointer hover:bg-zinc-800 transition-colors",
        otherMessage: "mb-2 p-2 rounded-lg bg-zinc-700 border border-zinc-600 cursor-pointer hover:bg-zinc-600 transition-colors",
        icon: "w-3 h-3 text-gray-400 flex-shrink-0",
        username: "text-xs font-semibold text-white",
        content: "text-xs text-gray-300 truncate"
      },
      {
        name: "Minimal Glow Line",
        myMessage: "mb-2 p-2 rounded-md bg-white/5 border-l-2 border-cyan-500 cursor-pointer hover:bg-white/10 transition-colors",
        otherMessage: "mb-2 p-2 rounded-md bg-zinc-700 border-l-2 border-cyan-500 cursor-pointer hover:bg-zinc-600 transition-colors",
        icon: "w-3 h-3 text-cyan-400 flex-shrink-0",
        username: "text-xs font-semibold text-white",
        content: "text-xs text-gray-300 truncate"
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
                Reply Context Theme Demo
              </h1>
              <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                Choose your preferred reply style - tested in both your messages (blue) and other messages (gray)
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
        <div className="space-y-8">
          {currentStyles.map((style, index) => (
            <div key={index} className={`rounded-xl p-6 ${isDarkMode ? 'bg-zinc-800' : 'bg-white'} shadow-lg`}>
              <h2 className={`text-lg font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                Style {index + 1}: {style.name}
              </h2>

              <div className="grid md:grid-cols-2 gap-6">
                {/* Your Message (Blue Bubble) */}
                <div>
                  <h3 className={`text-sm font-semibold mb-3 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                    Your Message (Blue)
                  </h3>
                  <div className="flex justify-end">
                    <div className="max-w-[85%] p-4 rounded-xl bg-blue-600 text-white">
                      {/* Reply context preview */}
                      <div className={style.myMessage}>
                        <div className="flex items-center gap-1 mb-0.5">
                          <Reply className={style.icon} />
                          <span className={style.username}>
                            {sampleReply.username}
                          </span>
                        </div>
                        <p className={style.content}>
                          {sampleReply.content}
                        </p>
                      </div>

                      {/* Message content */}
                      <div className="mt-1">
                        {sampleMessage}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Other User Message (Gray Bubble) */}
                <div>
                  <h3 className={`text-sm font-semibold mb-3 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                    Other User (Gray)
                  </h3>
                  <div className="flex justify-start">
                    <div className={`max-w-[85%] p-4 rounded-xl ${isDarkMode ? 'bg-zinc-700 text-white' : 'bg-gray-200 text-gray-900'}`}>
                      {/* Reply context preview */}
                      <div className={style.otherMessage}>
                        <div className="flex items-center gap-1 mb-0.5">
                          <Reply className={style.icon} />
                          <span className={style.username}>
                            {sampleReply.username}
                          </span>
                        </div>
                        <p className={style.content}>
                          {sampleReply.content}
                        </p>
                      </div>

                      {/* Message content */}
                      <div className="mt-1">
                        {sampleMessage}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Style details */}
              <details className="mt-4">
                <summary className={`cursor-pointer text-sm font-medium ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} hover:underline`}>
                  View CSS Classes
                </summary>
                <div className={`mt-2 p-3 rounded text-xs font-mono ${isDarkMode ? 'bg-zinc-900 text-gray-300' : 'bg-gray-50 text-gray-700'} overflow-x-auto`}>
                  <div className="space-y-2">
                    <div><strong>Your Message Container:</strong> <br/>{style.myMessage}</div>
                    <div><strong>Other Message Container:</strong> <br/>{style.otherMessage}</div>
                    <div><strong>Icon:</strong> {style.icon}</div>
                    <div><strong>Username:</strong> {style.username}</div>
                    <div><strong>Content:</strong> {style.content}</div>
                  </div>
                </div>
              </details>
            </div>
          ))}
        </div>

        {/* Notes Section */}
        <div className={`mt-12 p-6 rounded-xl ${isDarkMode ? 'bg-zinc-800' : 'bg-white'} shadow-lg`}>
          <h2 className={`text-lg font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
            Design Considerations
          </h2>
          <ul className={`space-y-2 text-sm ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>
            <li className="flex items-start gap-2">
              <span className="text-green-500 font-bold">✓</span>
              <span><strong>Dual Context:</strong> Each style has separate styling for blue bubbles (your messages) and gray bubbles (other users)</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 font-bold">✓</span>
              <span><strong>Contrast:</strong> All styles maintain high contrast in both bubble contexts</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 font-bold">✓</span>
              <span><strong>Clickability:</strong> Hover states indicate interactive elements</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 font-bold">✓</span>
              <span><strong>Visual Hierarchy:</strong> Username and content are clearly differentiated</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 font-bold">✓</span>
              <span><strong>Consistency:</strong> Reply context is visually distinct from message content</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
