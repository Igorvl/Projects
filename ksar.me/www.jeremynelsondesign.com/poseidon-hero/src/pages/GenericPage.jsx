import React from 'react'
import { motion } from 'framer-motion'

export default function GenericPage({ title }) {
    return (
        <motion.div
            className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-20 text-white"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
        >
            <h1 className="text-6xl font-light tracking-[0.3em] uppercase mb-10">{title}</h1>
            <div className="w-20 h-1 bg-white/20 mb-10" />
            <p className="text-gray-500 max-w-xl text-center leading-relaxed">
                This section is under development. Exploring the intersection of digital craft and physical form.
            </p>
        </motion.div>
    )
}
