"use client";

import React, { createContext, useContext, useState, useCallback } from "react";
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

type ToastType = "success" | "error" | "info" | "warning";

interface Toast {
    id: string;
    message: string;
    type: ToastType;
}

interface ToastContextType {
    toast: (message: string, type?: ToastType) => void;
    success: (message: string) => void;
    error: (message: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const useToast = () => {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error("useToast must be used within a ToastProvider");
    }
    return context;
};

export const ToastProvider = ({ children }: { children: React.ReactNode }) => {
    const [toasts, setToasts] = useState<Toast[]>([]);

    const addToast = useCallback((message: string, type: ToastType = "info") => {
        const id = Math.random().toString(36).substring(2, 9);
        setToasts((prev) => [...prev, { id, message, type }]);

        setTimeout(() => {
            setToasts((prev) => prev.filter((t) => t.id !== id));
        }, 3000);
    }, []);

    const toast = useCallback((message: string, type: ToastType = "info") => {
        addToast(message, type);
    }, [addToast]);

    const success = useCallback((message: string) => {
        addToast(message, "success");
    }, [addToast]);

    const error = useCallback((message: string) => {
        addToast(message, "error");
    }, [addToast]);

    return (
        <ToastContext.Provider value={{ toast, success, error }}>
            {children}
            <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
                <AnimatePresence>
                    {toasts.map((t) => (
                        <ToastItem key={t.id} {...t} onClose={() => setToasts((prev) => prev.filter((i) => i.id !== t.id))} />
                    ))}
                </AnimatePresence>
            </div>
        </ToastContext.Provider>
    );
};

const ToastItem = ({ id, message, type, onClose }: Toast & { onClose: () => void }) => {
    const icons = {
        success: <CheckCircle className="text-green-400" size={20} />,
        error: <AlertCircle className="text-red-400" size={20} />,
        warning: <AlertCircle className="text-yellow-400" size={20} />,
        info: <Info className="text-blue-400" size={20} />,
    };

    const bgColors = {
        success: "bg-green-500/10 border-green-500/20",
        error: "bg-red-500/10 border-red-500/20",
        warning: "bg-yellow-500/10 border-yellow-500/20",
        info: "bg-blue-500/10 border-blue-500/20",
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: -20, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.2 } }}
            layout
            className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-md shadow-lg min-w-[300px] max-w-md ${bgColors[type]}`}
        >
            {icons[type]}
            <p className="flex-1 text-sm font-medium text-slate-200">{message}</p>
            <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
                <X size={16} />
            </button>
        </motion.div>
    );
};
