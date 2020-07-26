import React from "react";
import {Redirect} from "react-router-dom";

export default (Component) => {
	
	let RedirectComponent = (props) => {
		if (!props.isLoggedIn) return <Redirect to={'/login'}/>;
		return <Component {...props}/>
	};
	
	return <RedirectComponent/>
}