"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import { Plus, Rocket, FileText, ChevronRight, Activity, Settings } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const API_BASE = "http://127.0.0.1:8000";

export default function Home() {
  const [projects, setProjects] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [newProject, setNewProject] = useState({ name: "", prompt: "" });

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const res = await axios.get(`${API_BASE}/projects`);
      setProjects(res.data);
    } catch (e) {
      console.error("Fetch projects failed", e);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newProject.name) return;
    const formData = new FormData();
    formData.append("name", newProject.name);
    formData.append("prompt", newProject.prompt || "你是一个意图分类专家，请根据用户的输入进行分类。");

    try {
      await axios.post(`${API_BASE}/projects`, formData);
      setNewProject({ name: "", prompt: "" });
      setShowCreate(false);
      fetchProjects();
    } catch (e) {
      alert("创建失败");
    }
  };

  return (
    <div className="max-w-6xl mx-auto">
      <header className="flex justify-between items-center mb-12">
        <div>
          <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
            Prompt Optimizer
          </h1>
          <p className="text-slate-400 mt-2">智能提示词优化与意图识别评测平台</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 transition-colors px-6 py-3 rounded-xl font-medium shadow-lg shadow-blue-900/20"
        >
          <Plus size={20} />
          新建项目
        </button>
      </header>

      {loading ? (
        <div className="flex justify-center py-20">
          <Activity className="animate-spin text-blue-500" size={40} />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <AnimatePresence>
            {projects.map((p) => (
              <motion.div
                key={p.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass p-6 rounded-2xl group hover:border-white/20 transition-all cursor-pointer"
                onClick={() => window.location.href = `/project/${p.id}`}
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="p-3 bg-blue-500/10 rounded-xl text-blue-400">
                    <Rocket size={24} />
                  </div>
                  <ChevronRight size={20} className="text-slate-600 group-hover:text-slate-400 group-hover:translate-x-1 transition-all" />
                </div>
                <h3 className="text-xl font-semibold mb-2 group-hover:text-blue-400 transition-colors">{p.name}</h3>
                <p className="text-slate-400 text-sm line-clamp-2 mb-4">
                  {p.current_prompt}
                </p>
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <Activity size={12} />
                    {p.iterations?.length || 0} 次优化
                  </span>
                  <span>{new Date(p.created_at).toLocaleDateString()}</span>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="glass w-full max-w-lg p-8 rounded-3xl"
          >
            <h2 className="text-2xl font-bold mb-6">创建新项目</h2>
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">项目名称</label>
                <input
                  type="text"
                  value={newProject.name}
                  onChange={e => setNewProject({ ...newProject, name: e.target.value })}
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                  placeholder="例如：意图分类优化"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">初始提示词</label>
                <textarea
                  value={newProject.prompt}
                  onChange={e => setNewProject({ ...newProject, prompt: e.target.value })}
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors h-32 resize-none"
                  placeholder="请输入初始提示词..."
                />
              </div>
              <div className="flex gap-4">
                <button
                  onClick={() => setShowCreate(false)}
                  className="flex-1 px-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors font-medium border border-white/10"
                >
                  取消
                </button>
                <button
                  onClick={handleCreate}
                  className="flex-1 bg-blue-600 hover:bg-blue-500 px-6 py-3 rounded-xl font-medium transition-colors shadow-lg shadow-blue-900/20"
                >
                  创建
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
