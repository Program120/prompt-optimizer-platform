"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import { Plus, Rocket, FileText, ChevronRight, Activity, Settings, Trash2, Database, Copy, Layers } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import GlobalModelsConfig from "./components/GlobalModelsConfig";
import TestOutputModal from "./components/TestOutputModal";

// 统一使用相对路径，由 Next.js rewrites 转发到后端
const API_BASE = "/api";

export default function Home() {
  const [projects, setProjects] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [newProject, setNewProject] = useState({ name: "", prompt: "", projectType: "single" as "single" | "multi" });
  const [copySourceProject, setCopySourceProject] = useState<any>(null);

  const [deleteModal, setDeleteModal] = useState<{ show: boolean; projectId: string | null }>({ show: false, projectId: null });
  const [password, setPassword] = useState("");
  // 公共模型配置弹窗状态
  const [showGlobalModels, setShowGlobalModels] = useState<boolean>(false);
  const [showTestModal, setShowTestModal] = useState(false);

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
    formData.append("project_type", newProject.projectType);

    try {
      const res = await axios.post(`${API_BASE}/projects`, formData);
      const createdProject = res.data;

      // 如果是拷贝项目，则需要把源项目的配置更新过去（使用 JSON body 格式）
      if (copySourceProject && createdProject.id) {
        // 构建 JSON 请求体（匹配后端 ProjectUpdateRequest 模型）
        const updateData: Record<string, any> = {
          current_prompt: newProject.prompt || createdProject.current_prompt
        };

        // 1. 基础配置映射
        if (copySourceProject.config) {
          const cfg = copySourceProject.config;
          if (cfg.query_col) updateData.query_col = cfg.query_col;
          if (cfg.target_col) updateData.target_col = cfg.target_col;
          if (cfg.reason_col) updateData.reason_col = cfg.reason_col;
          if (cfg.extract_field) updateData.extract_field = cfg.extract_field;
          if (cfg.validation_limit) updateData.validation_limit = cfg.validation_limit;
          if (cfg.auto_iterate_config) updateData.auto_iterate_config = cfg.auto_iterate_config;
          // file_info 通常不拷贝，因为新文件需要重新上传
        }

        // 2. 模型配置
        if (copySourceProject.model_config) {
          updateData.model_cfg = copySourceProject.model_config;
        }

        // 3. 优化模型配置
        if (copySourceProject.optimization_model_config) {
          updateData.optimization_model_config = copySourceProject.optimization_model_config;
        }

        // 4. 优化提示词
        if (copySourceProject.optimization_prompt) {
          updateData.optimization_prompt = copySourceProject.optimization_prompt;
        }

        await axios.put(`${API_BASE}/projects/${createdProject.id}`, updateData, {
          headers: { "Content-Type": "application/json" }
        });
      }

      setNewProject({ name: "", prompt: "", projectType: "single" });
      setCopySourceProject(null);
      setShowCreate(false);
      fetchProjects();
    } catch (e: any) {
      alert("创建失败: " + (e.response?.data?.detail || e.message));
    }
  };

  const handleDelete = async () => {
    if (!deleteModal.projectId || !password) return;
    const formData = new FormData();
    formData.append("password", password);
    try {
      await axios.delete(`${API_BASE}/projects/${deleteModal.projectId}`, { data: formData, headers: { "Content-Type": "multipart/form-data" } });
      setDeleteModal({ show: false, projectId: null });
      setPassword("");
      fetchProjects();
    } catch (e: any) {
      alert(e.response?.data?.detail || "删除失败，请检查密码");
    }
  };

  const openCreateModal = () => {
    setCopySourceProject(null);
    setNewProject({ name: "", prompt: "", projectType: "single" });
    setShowCreate(true);
  };

  const openCopyModal = (e: any, project: any) => {
    e.stopPropagation();
    setCopySourceProject(project);
    setNewProject({
      name: `${project.name} - 副本`,
      prompt: project.current_prompt,
      projectType: project.config?.project_type || "single"
    });
    setShowCreate(true);
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
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowTestModal(true)}
            className="flex items-center gap-2 bg-purple-600/20 hover:bg-purple-600/30 text-purple-400 hover:text-purple-300 transition-colors px-4 py-3 rounded-xl font-medium border border-purple-500/30"
          >
            <Activity size={18} />
            测试 Playground
          </button>
          <button
            onClick={() => setShowGlobalModels(true)}
            className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 transition-colors px-4 py-3 rounded-xl font-medium border border-slate-600"
            title="管理公共模型配置"
          >
            <Database size={18} />
            公共模型
          </button>
          <button
            onClick={openCreateModal}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 transition-colors px-6 py-3 rounded-xl font-medium shadow-lg shadow-blue-900/20"
          >
            <Plus size={20} />
            新建项目
          </button>
        </div>
      </header>

      {loading ? (
        <div className="flex justify-center py-20">
          <Activity className="animate-spin text-blue-500" size={40} />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <AnimatePresence>
            {projects.map((p) => {
              const projectType = p.config?.project_type || "single";
              const isMultiRound = projectType === "multi";

              return (
                <motion.div
                  key={p.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="glass p-6 rounded-2xl group hover:border-white/20 transition-all cursor-pointer relative"
                  onClick={() => window.location.href = `/project/${p.id}`}
                >
                  <div className="flex justify-between items-start mb-4">
                    <div className={`p-3 rounded-xl ${isMultiRound ? "bg-purple-500/10 text-purple-400" : "bg-blue-500/10 text-blue-400"}`}>
                      {isMultiRound ? <Layers size={24} /> : <Rocket size={24} />}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-1 rounded-full ${isMultiRound ? "bg-purple-500/20 text-purple-400" : "bg-blue-500/20 text-blue-400"}`}>
                        {isMultiRound ? "多轮验证" : "单轮验证"}
                      </span>
                      <button
                        onClick={(e) => openCopyModal(e, p)}
                        className="p-1.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                        title="复制项目配置"
                      >
                        <Copy size={14} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteModal({ show: true, projectId: p.id });
                        }}
                        className="p-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                        title="删除项目"
                      >
                        <Trash2 size={14} />
                      </button>
                      <ChevronRight size={20} className="text-slate-600 group-hover:text-slate-400 group-hover:translate-x-1 transition-all" />
                    </div>
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
              );
            })}
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
            <h2 className="text-2xl font-bold mb-6">
              {copySourceProject ? "复制项目" : "创建新项目"}
            </h2>
            {copySourceProject && (
              <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl text-sm text-blue-300">
                正在复制项目 <strong>{copySourceProject.name}</strong> 的配置（包含模型参数、批处理配置等），不包含历史记录。
              </div>
            )}
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

              {/* 项目类型选择 */}
              {!copySourceProject && (
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">项目类型</label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setNewProject({ ...newProject, projectType: "single" })}
                      className={`p-4 rounded-xl border-2 transition-all text-left ${
                        newProject.projectType === "single"
                          ? "border-blue-500 bg-blue-500/10"
                          : "border-white/10 hover:border-white/20"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${newProject.projectType === "single" ? "bg-blue-500/20" : "bg-white/5"}`}>
                          <Rocket size={20} className="text-blue-400" />
                        </div>
                        <div>
                          <div className="font-medium">单轮验证</div>
                          <div className="text-xs text-slate-500 mt-0.5">单次请求验证</div>
                        </div>
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setNewProject({ ...newProject, projectType: "multi" })}
                      className={`p-4 rounded-xl border-2 transition-all text-left ${
                        newProject.projectType === "multi"
                          ? "border-purple-500 bg-purple-500/10"
                          : "border-white/10 hover:border-white/20"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${newProject.projectType === "multi" ? "bg-purple-500/20" : "bg-white/5"}`}>
                          <Layers size={20} className="text-purple-400" />
                        </div>
                        <div>
                          <div className="font-medium">多轮验证</div>
                          <div className="text-xs text-slate-500 mt-0.5">多轮对话验证</div>
                        </div>
                      </div>
                    </button>
                  </div>
                </div>
              )}

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
                  className={`flex-1 px-6 py-3 rounded-xl font-medium transition-colors shadow-lg ${
                    newProject.projectType === "multi"
                      ? "bg-purple-600 hover:bg-purple-500 shadow-purple-900/20"
                      : "bg-blue-600 hover:bg-blue-500 shadow-blue-900/20"
                  }`}
                >
                  {copySourceProject ? "复制并创建" : "创建"}
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}

      {/* Delete Modal */}
      {deleteModal.show && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="glass w-full max-w-md p-8 rounded-3xl"
          >
            <h2 className="text-2xl font-bold mb-2 text-red-500">删除项目</h2>
            <p className="text-slate-400 mb-6 text-sm">此操作不可恢复。请输入管理密码以确认删除。</p>
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">管理密码</label>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-red-500 transition-colors"
                  placeholder="请输入密码..."
                />
              </div>
              <div className="flex gap-4">
                <button
                  onClick={() => {
                    setDeleteModal({ show: false, projectId: null });
                    setPassword("");
                  }}
                  className="flex-1 px-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors font-medium border border-white/10"
                >
                  取消
                </button>
                <button
                  onClick={handleDelete}
                  className="flex-1 bg-red-600 hover:bg-red-500 px-6 py-3 rounded-xl font-medium transition-colors shadow-lg shadow-red-900/20"
                >
                  确认删除
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}

      {/* Global Models Config Modal */}
      {showGlobalModels && (
        <GlobalModelsConfig onClose={() => setShowGlobalModels(false)} />
      )}

      {showTestModal && (
        <TestOutputModal onClose={() => setShowTestModal(false)} />
      )}
    </div>
  );
}
