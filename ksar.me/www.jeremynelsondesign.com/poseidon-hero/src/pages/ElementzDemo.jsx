import React from 'react'

import { motion } from 'framer-motion'
import ElementzCrystal from '../components/ElementzCrystal'

export default function ElementzDemo() {
    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.8 }}
            className="w-full h-screen relative"
        >
            <ElementzCrystal />

            {/* UI Overlay */}
            <div className="absolute top-8 left-8 z-10 mix-blend-difference text-white">
                <a href="/" className="text-sm tracking-[0.2em] font-medium hover:opacity-50 transition-opacity">
                    ← BACK TO HOME
                </a>
                <h1 className="text-xs text-gray-400 mt-2 tracking-widest uppercase">
                    Refraction Study v1.0
                </h1>
            </div>
        </motion.div>
    )
}
