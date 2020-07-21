import React from "react";
import {Redirect} from "react-router-dom";

export default (Component) => {
	if (!props.isLoggedIn) return <Redirect to={'/login'}/>;
	return <Component/>
}