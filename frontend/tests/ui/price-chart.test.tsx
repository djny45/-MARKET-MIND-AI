import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createChart, createSeriesMarkers } from 'lightweight-charts'
import { setupUi } from './helpers'
import PriceChart from '../../src/PriceChart'

const bars = [
  { timestamp: '2026-01-02T00:00:00Z', open: 11, high: 13, low: 10, close: 12, volume: 120, source: 'local-csv', status: 'historical' },
  { timestamp: '2026-01-01T00:00:00Z', open: 10, high: 12, low: 9, close: 11, volume: 100, source: 'local-csv', status: 'historical' },
]

function chartInstance() {
  return vi.mocked(createChart).mock.results[0].value as any
}

describe('PriceChart component', () => {
  it('renders the manual-series heading, legend and source disclaimer', () => {
    setupUi(<PriceChart values={[10, 11, 12]} interval="1h" />)
    expect(screen.getByText('PRICE SERIES')).toBeInTheDocument()
    expect(screen.getByText(/· 1h/)).toBeInTheDocument()
    expect(screen.getByText(/NOT A LIVE QUOTE/)).toBeInTheDocument()
    expect(screen.getByText(/OHLC candles/)).toBeInTheDocument()
    expect(screen.getByText(/Volume uses an independent scale/)).toBeInTheDocument()

    expect(createChart).toHaveBeenCalledTimes(1)
    const chart = chartInstance()
    expect(chart.addSeries).toHaveBeenCalledTimes(3)
    const [candle, volume, line] = chart.addSeries.mock.results.map((result: any) => result.value)
    expect(candle.setData).toHaveBeenCalledWith([])
    expect(volume.setData).toHaveBeenCalledWith([])
    expect(line.setData).toHaveBeenCalledTimes(1)
    expect(line.setData.mock.calls[0][0]).toHaveLength(3)
    expect(chart.timeScale().fitContent).toHaveBeenCalled()
  })

  it('renders stored OHLCV metadata and wires sorted bars, volume and selection markers', () => {
    setupUi(<PriceChart
      bars={bars}
      interval="4h"
      retrievedAt="2026-01-03T00:00:00Z"
      selectedTimestamp="2026-01-01T00:00:00Z"
      selectedCluster={{ side: 'historical_swing_high', mean_price: 100, lower_price: 99, upper_price: 101, touch_count: 2, pivot_timestamps: [] }}
    />)
    expect(screen.getByText('STORED OHLCV HISTORY')).toBeInTheDocument()
    expect(screen.getByText(/local-csv · historical · RETRIEVED 2026-01-03T00:00:00Z/)).toBeInTheDocument()

    const chart = chartInstance()
    const [candle, volume, line] = chart.addSeries.mock.results.map((result: any) => result.value)
    const candleData = candle.setData.mock.calls[0][0]
    expect(candleData).toHaveLength(2)
    expect(candleData[0].open).toBe(10) // chronological order
    expect(volume.setData.mock.calls[0][0]).toHaveLength(2)

    const markers = vi.mocked(createSeriesMarkers).mock.results[0].value as any
    expect(markers.setMarkers).toHaveBeenCalledWith([expect.objectContaining({ text: 'Selected' })])
    expect(line.setData.mock.calls.at(-1)?.[0]).toEqual([
      expect.objectContaining({ value: 100 }),
      expect.objectContaining({ value: 100 }),
    ])
  })

  it('does not fabricate series data when both bars and values are empty', () => {
    setupUi(<PriceChart bars={[]} values={[]} />)
    expect(screen.getByText('PRICE SERIES')).toBeInTheDocument()
    expect(screen.getByText('NOT A LIVE QUOTE')).toBeInTheDocument()
    const chart = chartInstance()
    const [candle, volume, line] = chart.addSeries.mock.results.map((result: any) => result.value)
    expect(candle.setData).not.toHaveBeenCalled()
    expect(volume.setData).not.toHaveBeenCalled()
    expect(line.setData).not.toHaveBeenCalled()
  })

  it('disposes the chart on unmount', () => {
    const { unmount } = setupUi(<PriceChart values={[1, 2]} />)
    unmount()
    expect(chartInstance().remove).toHaveBeenCalledTimes(1)
  })
})
