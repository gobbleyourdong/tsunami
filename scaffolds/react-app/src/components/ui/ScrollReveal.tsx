import { useEffect, useRef, useState, ReactNode, isValidElement, Children, cloneElement } from "react"

type RevealDirection = "up" | "down" | "left" | "right" | "fade"

interface ScrollRevealProps {
  children: ReactNode
  direction?: RevealDirection
  animation?: RevealDirection | "slide-up" | "slide-down" | "slide-left" | "slide-right" | "fade-in"
  delay?: number     // ms
  duration?: number  // ms
  distance?: number  // px
  once?: boolean     // only animate once
  className?: string
}


// Tailwind classes that POSITION this element inside a grid parent.
// When a drone writes `<ScrollReveal><div className="lg:col-span-5">…
// </div></ScrollReveal>`, the grid sees ScrollReveal's wrapper as a
// default-width cell and the col-span on the nested div is invisible
// to the grid algorithm. We scan the single child's className for
// these prefixes and hoist them onto the wrapper so the grid sees
// the correct cell size.
//
// CRITICAL: this list is GRID-ITEM ONLY. `flex-col`, `w-full`,
// `w-1/3` etc are the element's OWN intrinsic layout; hoisting
// them breaks the child's internal children (v5 Models config
// overflowed after `flex-col` was promoted and the child lost
// its direction). Only prefixes that tell the GRID PARENT where
// to place this element are safe to hoist.
const LAYOUT_CLASS_RE =
  /(?:^|\s)((?:[a-z]+:)?(?:col-span-|col-start-|col-end-|row-span-|row-start-|row-end-|self-(?:auto|start|end|center|stretch|baseline)|justify-self-|place-self-|order-)[\w/.-]*)/g

const ANIM_TO_DIR: Record<string, RevealDirection> = {
  "slide-up": "up",
  "slide-down": "down",
  "slide-left": "left",
  "slide-right": "right",
  "fade-in": "fade",
  up: "up", down: "down", left: "left", right: "right", fade: "fade",
}

/** Reveal content on scroll into viewport. */
export function ScrollReveal({
  children,
  direction,
  animation,
  delay = 0,
  duration = 600,
  distance = 30,
  once = true,
  className,
}: ScrollRevealProps) {
  const dir: RevealDirection = direction ?? (animation ? ANIM_TO_DIR[animation] ?? "up" : "up")
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          if (once) observer.disconnect()
        } else if (!once) {
          setVisible(false)
        }
      },
      { threshold: 0.1 }
    )
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [once])

  const transforms: Record<string, string> = {
    up: `translateY(${distance}px)`,
    down: `translateY(-${distance}px)`,
    left: `translateX(${distance}px)`,
    right: `translateX(-${distance}px)`,
    fade: "none",
  }

  // Auto-hoist layout classes from a single child element. Drone-
  // written JSX like `<ScrollReveal><div className="lg:col-span-5">…</div>
  // </ScrollReveal>` should render the ScrollReveal wrapper as the
  // col-span-5 grid cell, not a default-sized cell containing a
  // col-span-5 div. We inspect the only child; if it's a single element
  // whose className contains layout-affecting classes, we move those
  // onto our wrapper.
  let hoistedClassName = className || ""
  let patchedChildren: ReactNode = children
  const kids = Children.toArray(children)
  if (kids.length === 1 && isValidElement(kids[0])) {
    const only = kids[0] as import("react").ReactElement<{ className?: string }>
    const childCls = only.props?.className || ""
    if (typeof childCls === "string" && childCls) {
      const hoisted: string[] = []
      const remaining = childCls.replace(LAYOUT_CLASS_RE, (m, cls) => {
        hoisted.push(cls)
        return " "
      }).replace(/\s+/g, " ").trim()
      if (hoisted.length > 0) {
        hoistedClassName = [className, ...hoisted].filter(Boolean).join(" ")
        // Re-clone the child with the layout classes stripped so they
        // don't double up (child would then re-apply col-span and fight
        // with the wrapper's grid-cell size).
        patchedChildren = cloneElement(only, { className: remaining || undefined })
      }
    }
  }

  return (
    <div ref={ref} className={hoistedClassName || undefined} style={{
      opacity: visible ? 1 : 0,
      transform: visible ? "none" : transforms[dir],
      transition: `opacity ${duration}ms ease ${delay}ms, transform ${duration}ms ease ${delay}ms`,
    }}>
      {patchedChildren}
    </div>
  )
}

export default ScrollReveal
