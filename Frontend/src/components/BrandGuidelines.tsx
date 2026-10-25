import { useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import type { Guideline } from '../App'

type BrandGuidelinesProps = {
  guidelines: Guideline[]
  setGuidelines: Dispatch<SetStateAction<Guideline[]>>
}

function BrandGuidelines({
  guidelines,
  setGuidelines,
}: BrandGuidelinesProps) {
  const [newGuideline, setNewGuideline] = useState('')
  const [guidelineType, setGuidelineType] = useState<'DO' | "DON'T">('DO')

  const addGuideline = () => {
    if (newGuideline.trim() === '') {
      return
    }

    const guideline: Guideline = {
      id: Date.now(),
      type: guidelineType,
      text: newGuideline.trim(),
    }

    setGuidelines((currentGuidelines) => [
      ...currentGuidelines,
      guideline,
    ])

    setNewGuideline('')
  }

  const deleteGuideline = (id: number) => {
    setGuidelines((currentGuidelines) =>
      currentGuidelines.filter((guideline) => guideline.id !== id)
    )
  }

  const dos = guidelines.filter(
    (guideline) => guideline.type === 'DO'
  )

  const donts = guidelines.filter(
    (guideline) => guideline.type === "DON'T"
  )

  return (
    <div>

      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold">
          Brand Guidelines
        </h1>

        <p className="mt-1 text-sm text-slate-400">
          Define the rules ENGANO uses when reviewing content.
        </p>
      </div>

      {/* Add Guideline */}
      <div className="mb-8 glass rounded-2xl p-6">

        <h2 className="text-lg font-semibold">
          Add a Guideline
        </h2>

        <p className="mt-1 text-sm text-slate-400">
          Create a rule that ENGANO should consider during content review.
        </p>

        <div className="mt-5 flex gap-3">

          <select
            value={guidelineType}
            onChange={(event) =>
              setGuidelineType(
                event.target.value as 'DO' | "DON'T"
              )
            }
            className="rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none focus:border-violet-400"
          >
            <option value="DO">DO</option>
            <option value="DON'T">DON'T</option>
          </select>

          <input
            type="text"
            value={newGuideline}
            onChange={(event) => setNewGuideline(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                addGuideline()
              }
            }}
            placeholder="e.g. Never use the word cheap."
            className="flex-1 rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-violet-400"
          />

          <button
            onClick={addGuideline}
            className="btn-primary px-5 py-3 text-sm"
          >
            Add Guideline
          </button>

        </div>

      </div>

      {/* Guidelines */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">

        {/* DO */}
        <div className="glass rounded-2xl p-6">

          <div className="mb-5 flex items-center justify-between">

            <div>
              <h2 className="text-lg font-semibold">
                DO
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                Practices your brand encourages.
              </p>
            </div>

            <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
              {dos.length} rules
            </span>

          </div>

          <div className="space-y-3">

            {dos.length === 0 && (
              <p className="rounded-lg border border-dashed border-slate-700 p-4 text-sm text-slate-500">
                No DO guidelines added yet.
              </p>
            )}

            {dos.map((guideline) => (

              <div
                key={guideline.id}
                className="flex items-start justify-between gap-4 rounded-lg border border-white/10 bg-slate-950/60 p-4"
              >

                <div className="flex gap-3">

                  <span className="mt-0.5 text-emerald-400">
                    ✓
                  </span>

                  <p className="text-sm leading-6 text-slate-300">
                    {guideline.text}
                  </p>

                </div>

                <button
                  onClick={() => deleteGuideline(guideline.id)}
                  className="text-xs text-slate-600 hover:text-red-400"
                >
                  Delete
                </button>

              </div>

            ))}

          </div>

        </div>

        {/* DON'T */}
        <div className="glass rounded-2xl p-6">

          <div className="mb-5 flex items-center justify-between">

            <div>
              <h2 className="text-lg font-semibold">
                DON'T
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                Practices your brand should avoid.
              </p>
            </div>

            <span className="rounded-full bg-red-500/10 px-3 py-1 text-xs font-medium text-red-400">
              {donts.length} rules
            </span>

          </div>

          <div className="space-y-3">

            {donts.length === 0 && (
              <p className="rounded-lg border border-dashed border-slate-700 p-4 text-sm text-slate-500">
                No DON'T guidelines added yet.
              </p>
            )}

            {donts.map((guideline) => (

              <div
                key={guideline.id}
                className="flex items-start justify-between gap-4 rounded-lg border border-white/10 bg-slate-950/60 p-4"
              >

                <div className="flex gap-3">

                  <span className="mt-0.5 text-red-400">
                    ×
                  </span>

                  <p className="text-sm leading-6 text-slate-300">
                    {guideline.text}
                  </p>

                </div>

                <button
                  onClick={() => deleteGuideline(guideline.id)}
                  className="text-xs text-slate-600 hover:text-red-400"
                >
                  Delete
                </button>

              </div>

            ))}

          </div>

        </div>

      </div>

      {/* Brand Library Notice */}
      <div className="mt-6 glass rounded-2xl p-5">

        <div className="flex gap-3">

          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-800">
            ℹ
          </div>

          <div>
            <h3 className="text-sm font-medium">
              Brand Library
            </h3>

            <p className="mt-1 text-sm leading-6 text-slate-400">
              These guidelines form part of the brand knowledge ENGANO uses
              when reviewing content.
            </p>
          </div>

        </div>

      </div>

    </div>
  )
}

export default BrandGuidelines
