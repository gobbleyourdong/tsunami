import React from "react"

interface BoxProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Box({ className = "", children, ...props }: BoxProps) {
  return (
    <div className={className} {...props}>
      {children}
    </div>
  )
}

export default Box
