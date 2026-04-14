import React from "react"

interface BoxProps extends React.HTMLAttributes<HTMLDivElement> {}

export default function Box({ className = "", children, ...props }: BoxProps) {
  return (
    <div className={className} {...props}>
      {children}
    </div>
  )
}
