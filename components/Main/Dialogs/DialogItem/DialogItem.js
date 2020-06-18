import React from 'react';
import s from '../../../../css/DialogsItem.module.css';
import {NavLink} from "react-router-dom";

export default (props) => {
	
	return (
		<div className={s.userItem}><NavLink to={'/dialogs/' + props.id}>{props.name}</NavLink></div>
	)
};


