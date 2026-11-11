import { useEffect, useRef } from 'react'
import * as THREE from 'three'

type Props = { profileCount: number; activityCount: number }

function pointOnSphere(lat: number, lon: number, radius: number) {
  const phi = (90 - lat) * Math.PI / 180
  const theta = (lon + 180) * Math.PI / 180
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  )
}

export default function GlobalResearchGlobe({ profileCount, activityCount }: Props) {
  const host = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const element = host.current
    if (!element) return
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' })
    } catch {
      element.dataset.webgl = 'unavailable'
      return
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
    renderer.setClearColor(0x000000, 0)
    element.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100)
    camera.position.set(0, 0, 7.2)
    const globe = new THREE.Group()
    scene.add(globe)

    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(2, 48, 32),
      new THREE.MeshBasicMaterial({ color: 0x061d36, wireframe: true, transparent: true, opacity: 0.52 })
    )
    globe.add(sphere)

    const pointPositions: number[] = []
    for (let i = 0; i < 520; i++) {
      const y = 1 - (i / 519) * 2
      const radius = Math.sqrt(1 - y * y)
      const angle = Math.PI * (3 - Math.sqrt(5)) * i
      pointPositions.push(Math.cos(angle) * radius * 2.015, y * 2.015, Math.sin(angle) * radius * 2.015)
    }
    const pointGeometry = new THREE.BufferGeometry()
    pointGeometry.setAttribute('position', new THREE.Float32BufferAttribute(pointPositions, 3))
    globe.add(new THREE.Points(pointGeometry, new THREE.PointsMaterial({ color: 0x22c8ff, size: 0.025, transparent: true, opacity: 0.86 })))

    const ringMaterial = new THREE.LineBasicMaterial({ color: 0x167cb8, transparent: true, opacity: 0.5 })
    for (let lat = -60; lat <= 60; lat += 30) {
      const points: THREE.Vector3[] = []
      for (let lon = -180; lon <= 180; lon += 4) points.push(pointOnSphere(lat, lon, 2.006))
      globe.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), ringMaterial))
    }
    for (let lon = -180; lon < 180; lon += 30) {
      const points: THREE.Vector3[] = []
      for (let lat = -90; lat <= 90; lat += 3) points.push(pointOnSphere(lat, lon, 2.006))
      globe.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), ringMaterial))
    }

    const arcMaterial = new THREE.LineBasicMaterial({ color: 0xb56cff, transparent: true, opacity: 0.78 })
    const routes = [[18,-75,51,0],[-33,151,37,127],[19,72,40,-74],[1,103,48,2],[-23,-46,35,139]]
    routes.forEach(([lat1,lon1,lat2,lon2]) => {
      const start = pointOnSphere(lat1,lon1,2.02)
      const end = pointOnSphere(lat2,lon2,2.02)
      const mid = start.clone().add(end).multiplyScalar(0.5).normalize().multiplyScalar(2.72)
      const curve = new THREE.QuadraticBezierCurve3(start,mid,end)
      globe.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(48)),arcMaterial))
      const marker = new THREE.Mesh(new THREE.SphereGeometry(0.045,10,8),new THREE.MeshBasicMaterial({color:0x6be7ff}))
      marker.position.copy(end)
      globe.add(marker)
    })

    const halo = new THREE.Mesh(new THREE.TorusGeometry(2.22,0.012,6,120),new THREE.MeshBasicMaterial({color:0x237fe5,transparent:true,opacity:0.72}))
    halo.rotation.x = Math.PI * 0.5
    globe.add(halo)

    const resize = () => {
      const width = Math.max(1,element.clientWidth)
      const height = Math.max(1,element.clientHeight)
      renderer.setSize(width,height,false)
      camera.aspect = width/height
      camera.updateProjectionMatrix()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(element)
    resize()
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let raf = 0
    let dragging = false
    let lastX = 0
    let lastY = 0
    const pointerDown = (event: PointerEvent) => {
      dragging = true
      lastX = event.clientX
      lastY = event.clientY
      element.setPointerCapture(event.pointerId)
      element.classList.add('is-dragging')
    }
    const pointerMove = (event: PointerEvent) => {
      if (!dragging) return
      const deltaX = event.clientX - lastX
      const deltaY = event.clientY - lastY
      lastX = event.clientX
      lastY = event.clientY
      globe.rotation.y += deltaX * 0.006
      globe.rotation.x = THREE.MathUtils.clamp(globe.rotation.x + deltaY * 0.004, -0.65, 0.65)
      if (reducedMotion && !raf) raf = requestAnimationFrame(render)
    }
    const pointerUp = (event: PointerEvent) => {
      dragging = false
      element.classList.remove('is-dragging')
      if (element.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId)
    }
    element.addEventListener('pointerdown', pointerDown)
    element.addEventListener('pointermove', pointerMove)
    element.addEventListener('pointerup', pointerUp)
    element.addEventListener('pointercancel', pointerUp)
    function render() {
      raf = 0
      if (!reducedMotion && !dragging) globe.rotation.y += 0.0018
      renderer.render(scene,camera)
      if (!reducedMotion || dragging) raf = requestAnimationFrame(render)
    }
    render()

    return () => {
      cancelAnimationFrame(raf)
      element.removeEventListener('pointerdown', pointerDown)
      element.removeEventListener('pointermove', pointerMove)
      element.removeEventListener('pointerup', pointerUp)
      element.removeEventListener('pointercancel', pointerUp)
      observer.disconnect()
      scene.traverse(object => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.Points) {
          object.geometry.dispose()
          const material = object.material
          if (Array.isArray(material)) material.forEach(item => item.dispose())
          else material.dispose()
        }
      })
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [])

  return <section className="global-globe-panel" aria-label="Three-dimensional global research network">
    <div className="global-globe-copy"><span className="eyebrow">GLOBAL RESEARCH TOPOLOGY</span><h2>Market intelligence, visualized in 3D</h2><p>Rotating network illustration. It visualizes registered profiles, not live exchange connectivity.</p><div className="global-globe-metrics"><span><b>{profileCount}</b><small>REGISTERED PROFILES</small></span><span><b>{activityCount}</b><small>RECORDED TASKS</small></span><span><b>1</b><small>SHARED CORE</small></span></div></div>
    <div className="global-globe-canvas" ref={host} role="img" aria-label="Rotating wireframe globe with research connection arcs"><div className="global-globe-fallback">3D globe requires WebGL support</div></div>
    <div className="global-globe-tag">THREE.JS · MOTION-ENABLED TERMINAL</div>
  </section>
}
