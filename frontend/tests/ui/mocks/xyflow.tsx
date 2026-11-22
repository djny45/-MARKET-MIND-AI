import { useState, type ReactNode } from 'react'

export const Position = { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' } as const

type Handler = (...args: any[]) => void
let onConnectHandler: Handler | undefined
let onNodesChangeHandler: Handler | undefined
let onEdgesChangeHandler: Handler | undefined

/** Test-only escape hatch for exercising handlers that require real canvas gestures. */
export const __flowTest = {
  connect(connection: { source: string; target: string }) {
    onConnectHandler?.(connection)
  },
  nodesChange(changes: unknown[]) {
    onNodesChangeHandler?.(changes)
  },
  edgesChange(changes: unknown[]) {
    onEdgesChangeHandler?.(changes)
  },
  reset() {
    onConnectHandler = undefined
    onNodesChangeHandler = undefined
    onEdgesChangeHandler = undefined
  },
}

export function Handle({ type, position }: { type: string; position: string }) {
  return <span data-testid={`flow-handle-${type}`} data-position={position} />
}

export function Background() {
  return <div data-testid="flow-background" />
}

export function MiniMap() {
  return <div data-testid="flow-minimap" />
}

export function Controls() {
  return <div data-testid="flow-controls" />
}

type FlowNode = { id: string; type?: string; data?: any; selected?: boolean }
type FlowProps = {
  nodes?: FlowNode[]
  edges?: unknown[]
  children?: ReactNode
  nodeTypes?: Record<string, (props: any) => ReactNode>
  onNodeClick?: Handler
  onConnect?: Handler
  onNodesChange?: Handler
  onEdgesChange?: Handler
}

export function ReactFlow({ nodes = [], edges = [], children, nodeTypes = {}, onNodeClick, onConnect, onNodesChange, onEdgesChange }: FlowProps) {
  onConnectHandler = onConnect
  onNodesChangeHandler = onNodesChange
  onEdgesChangeHandler = onEdgesChange
  return (
    <div data-testid="react-flow" data-node-count={nodes.length} data-edge-count={edges.length}>
      {nodes.map(node => {
        const NodeComponent = nodeTypes[node.type || 'default'] ?? (({ data }: any) => <span>{String(data?.label ?? '')}</span>)
        return (
          <div
            key={node.id}
            data-testid={`flow-node-${node.id}`}
            data-node-id={node.id}
            onClick={event => onNodeClick?.(event, node)}
          >
            <NodeComponent data={node.data ?? {}} selected={Boolean(node.selected)} id={node.id} />
          </div>
        )
      })}
      {children}
    </div>
  )
}

export function addEdge(connection: { source: string; target: string }, edges: any[]) {
  if (edges.some(edge => edge.source === connection.source && edge.target === connection.target)) return edges
  return [...edges, { ...connection, id: `edge-${edges.length + 1}` }]
}

export function useNodesState<T>(initial: T[]): [T[], (value: T[] | ((previous: T[]) => T[])) => void, Handler] {
  const [nodes, setNodes] = useState<T[]>(initial)
  return [nodes, setNodes, () => {}] as [T[], typeof setNodes, Handler]
}

export function useEdgesState<T>(initial: T[]): [T[], (value: T[] | ((previous: T[]) => T[])) => void, Handler] {
  const [edges, setEdges] = useState<T[]>(initial)
  return [edges, setEdges, () => {}] as [T[], typeof setEdges, Handler]
}
