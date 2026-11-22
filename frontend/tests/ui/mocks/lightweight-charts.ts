import { vi } from 'vitest'

export const ColorType = { Solid: 'solid' } as const
export const CandlestickSeries = 'candlestick'
export const LineSeries = 'line'
export const HistogramSeries = 'histogram'

export const createSeriesMarkers = vi.fn(() => ({ setMarkers: vi.fn() }))

const makeSeries = () => ({ setData: vi.fn(), applyOptions: vi.fn(), priceLineVisible: false })

export const createChart = vi.fn(() => {
  const priceScale = { applyOptions: vi.fn() }
  const timeScale = { fitContent: vi.fn() }
  return {
    addSeries: vi.fn(() => ({ setData: vi.fn(), applyOptions: vi.fn() })),
    priceScale: vi.fn(() => priceScale),
    timeScale: vi.fn(() => timeScale),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  }
})

export { makeSeries }
