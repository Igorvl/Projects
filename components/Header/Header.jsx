import React from 'react'
import cls from './Header.module.css'

export default () => {
  return (
    <header className={cls.header}>
      <img src={require('./logo.png')} alt="" />
      {/* <img src="https://storage.needpix.com/rsynced_images/lion-309219_1280.png" alt="" /> */}
    </header>
  )
}
