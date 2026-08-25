import { useRef, useState } from 'react'

export function useTilt() {
  const ref = useRef(null)
  const [style, setStyle] = useState({})
  const onMove = (event) => {
    const box = ref.current?.getBoundingClientRect()
    if (!box) return
    const x = (event.clientX - box.left) / box.width - 0.5
    const y = (event.clientY - box.top) / box.height - 0.5
    setStyle({
      transform: `perspective(900px) rotateX(${y * -4}deg) rotateY(${x * 5}deg) translateZ(4px)`,
    })
  }
  return { ref, style, onMouseMove: onMove, onMouseLeave: () => setStyle({}) }
}

export function Panel({ children, className = '', tilt = true, style: customStyle = {} }) {
  const props = useTilt()
  return (
    <section
      ref={props.ref}
      className={`panel ${className}`}
      style={{ ...(tilt ? props.style : {}), ...customStyle }}
      onMouseMove={tilt ? props.onMouseMove : undefined}
      onMouseLeave={tilt ? props.onMouseLeave : undefined}
    >
      {children}
    </section>
  )
}
