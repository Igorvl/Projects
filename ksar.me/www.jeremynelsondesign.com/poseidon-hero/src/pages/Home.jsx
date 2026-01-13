import React from 'react'
import HeroSection from '../components/HeroSection'

export default function Home() {
    return (
        <main className="relative">
            <HeroSection />

            {/* Video Section */}
            <section className="relative w-full h-screen bg-black overflow-hidden">
                <video
                    src="/extslowWater.mp4"
                    autoPlay
                    muted
                    loop
                    playsInline
                    className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-black/20" />
            </section>

            {/* Concept Section */}
            <section className="min-h-screen bg-neutral-900 flex flex-col items-center justify-center py-20 gap-20">
                <div className="text-overlap w-1/2 mx-auto">
                    <h2 className="text-4xl text-white font-light mb-8">Concept</h2>
                    <p className="text-xl text-gray-400 leading-relaxed">
                        The intersection of synthetic biology and digital architecture creates a new paradigm
                        for living spaces. We design environments that breathe, adapt, and evolve with their inhabitants.
                    </p>
                </div>

                <div className="w-full h-[50vh] bg-neutral-800" />

                <div className="text-overlap w-1/2 mx-auto text-right">
                    <h2 className="text-4xl text-white font-light mb-8">Philosophy</h2>
                    <p className="text-xl text-gray-400 leading-relaxed">
                        Beyond the static confines of traditional concrete, we explore fluid dynamics
                        and organic structural integrity.
                    </p>
                </div>
            </section>
        </main>
    )
}
