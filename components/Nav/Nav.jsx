import React from 'react'
import cls from './Nav.module.css'

export default () => {
  return (
    <nav className={cls.nav}>
      <ul className={cls.nav__list}>
        <li className={cls.nav__item}><a className={cls.nav__link} href='#s'>Profile</a></li>
        <li className={cls.nav__item}><a className={cls.nav__link} href='#s'>Messages</a></li>
        <li className={cls.nav__item}><a className={cls.nav__link} href='#s'>News</a></li>
        <li className={cls.nav__item}><a className={cls.nav__link} href='#s'>Music</a></li>
        <li className={cls.nav__item}><a className={cls.nav__link} href='#s'>Settings</a></li>
      </ul>
    </nav>
  )
}